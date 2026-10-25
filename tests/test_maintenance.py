import calendar
import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

from hippos_analyst import api, collector, maintenance, store
from test_collector import Clock, response


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.db = store.connect(Path(self.temp.name)/'archive.sqlite3')
        self.clock = Clock()
        self.today = '2026-10-25'

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def calendar(self, day, done=False):
        path = api.calendar_path(day)
        store.enqueue(self.db,path,'calendar',{'date':day})
        if done:
            self.db.execute("UPDATE jobs SET status='done',last_success=? WHERE path=?",(self.clock(),path))
        return path

    def test_refresh_age_and_pending_cooldown_are_preserved(self):
        path=self.calendar(self.today,True)
        c={'date':self.today}
        self.assertEqual(store.enqueue_refresh(self.db,path,'calendar',c,10,self.clock()),0)
        self.clock.now+=86400
        self.assertEqual(store.enqueue_refresh(self.db,path,'calendar',c,10,self.clock()),1)
        self.db.execute("UPDATE jobs SET attempts=2,next_attempt=12345,last_error='HTTP 503' WHERE path=?",(path,))
        self.assertEqual(store.enqueue_refresh(self.db,path,'calendar',c,10,self.clock()),0)
        row=self.db.execute('SELECT * FROM jobs WHERE path=?',(path,)).fetchone()
        self.assertEqual((row['attempts'],row['next_attempt'],row['last_error']),(2,12345,'HTTP 503'))
        self.db.execute("UPDATE jobs SET status='failed' WHERE path=?",(path,))
        self.assertEqual(store.enqueue_refresh(self.db,path,'calendar',c,10,self.clock()+90000),0)
        self.assertEqual(self.db.execute('SELECT status FROM jobs').fetchone()[0],'failed')

    def test_refresh_window_and_idempotence(self):
        self.calendar('2026-09-30') # Keep existing history work; do not expand another month.
        with self.db: first=maintenance.prepare(self.db,self.today,self.clock())
        self.assertEqual(first['refresh'],11)
        days=[json.loads(r[0])['date'] for r in self.db.execute("SELECT context FROM jobs WHERE json_extract(context,'$.refresh_after') IS NOT NULL")]
        self.assertEqual((min(days),max(days)),('2026-10-22','2026-11-01'))
        with self.db: second=maintenance.prepare(self.db,self.today,self.clock())
        self.assertEqual(second['refresh'],0)

    def test_pause_failure_and_budget_block_all_scheduling(self):
        self.db.execute("UPDATE control SET paused_reason='HTTP 429'")
        self.assertEqual(maintenance.run(self.db,self.today,clock=self.clock,emit=lambda _:None),'paused')
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],0)
        self.db.execute('UPDATE control SET paused_reason=NULL,paused_until=?',(self.clock()+100,))
        self.assertEqual(maintenance.run(self.db,self.today,clock=self.clock),'retry')
        self.db.execute('UPDATE control SET paused_until=0')
        path=self.calendar(self.today)
        self.db.execute("UPDATE jobs SET status='failed'")
        self.assertEqual(maintenance.run(self.db,self.today,clock=self.clock),'failed')
        self.db.execute("UPDATE jobs SET status='done'")
        for _ in range(200):self.db.execute("INSERT INTO requests(path,started_at) VALUES('test',?)",(self.clock(),))
        self.assertEqual(maintenance.run(self.db,self.today,clock=self.clock,emit=lambda _:None),'budget')
        self.assertEqual(self.db.execute('SELECT count(*) FROM jobs').fetchone()[0],1)

    def test_history_fills_october_before_september_despite_old_sample(self):
        self.calendar('2025-10-22',True)
        result=maintenance.seed_history(self.db)
        self.assertEqual((result['month'],result['queued']),('2026-10',31))
        self.db.execute("UPDATE jobs SET status='done',last_success=?",(self.clock(),))
        result=maintenance.seed_history(self.db)
        self.assertEqual((result['month'],result['queued']),('2026-09',30))

    def test_unfinished_month_fields_prevent_advancing_frontier(self):
        for n in range(31):self.calendar((date(2026,10,1)+timedelta(days=n)).isoformat(),True)
        store.enqueue_refresh(self.db,api.runners_path(self.today,'H','1'),'runners',{'date':self.today,'track':'H','number':'1'},10,self.clock())
        result=maintenance.seed_history(self.db)
        self.assertEqual(result['reason'],'month_pending')
        self.assertEqual(result['queued'],0)

    def test_pending_refresh_does_not_erase_observed_history_frontier(self):
        for n in range(31):self.calendar((date(2026,10,1)+timedelta(days=n)).isoformat(),True)
        store.enqueue_refresh(self.db,api.calendar_path(self.today),'calendar',{'date':self.today},10,self.clock()+86400)
        result=maintenance.seed_history(self.db)
        self.assertEqual((result['month'],result['queued']),('2026-09',30))

    def test_history_stops_after_twelve_consecutive_empty_months(self):
        month=date(2026,10,1)
        for _ in range(12):
            for n in range(calendar.monthrange(month.year,month.month)[1]):
                self.calendar((month+timedelta(days=n)).isoformat(),True)
            month=(month-timedelta(days=1)).replace(day=1)
        result=maintenance.seed_history(self.db)
        self.assertEqual(result['reason'],'twelve_empty_months')
        self.assertEqual(result['queued'],0)

    def test_profile_seeds_are_once_per_day_and_only_known_participants(self):
        # Minimal normalized records create actual participant identities.
        with self.db:
            self.db.execute("INSERT INTO meetings VALUES(?,?,?,?,?,?,?,?)",(self.today,'H','test','12:00','H',0,'{}',0))
            self.db.execute("INSERT INTO races VALUES(?,?,?,?,?,?,?,?)",(self.today,'H','1','L','auto','2100','{}',0))
            for n in range(1,9):
                self.db.execute('INSERT INTO horses VALUES(?,?,?,?,?)',(str(n),'Horse','L','FI',0))
                self.db.execute('INSERT INTO entries VALUES(?,?,?,?,?,?,?,?,?,?,?)',(self.today,'H','1',str(n),str(n),None,None,None,False,'{}',0))
            self.db.execute("INSERT INTO horses VALUES('999','Ancestor',NULL,NULL,0)")
            result=maintenance.prepare(self.db,self.today,self.clock())
        self.assertEqual(result['profiles'],5)
        self.assertFalse(self.db.execute("SELECT 1 FROM jobs WHERE path='/horse/999'").fetchone())
        self.db.execute("UPDATE jobs SET status='done' WHERE kind='profile'")
        self.assertEqual(maintenance.prepare(self.db,self.today,self.clock())['profiles'],0)
        self.assertEqual(maintenance.prepare(self.db,'2026-10-26',self.clock()+86400)['profiles'],3)

    def test_each_queue_gets_a_share_and_transient_stops_whole_wakeup(self):
        with self.db:
            self.calendar('2026-09-30')
            store.enqueue_profile(self.db,'100',0)
        calls=[]
        def fetch(path):
            calls.append((path,self.clock()))
            return response({'id':'100','name':'Horse'} if path.startswith('/horse/') else [])
        result=maintenance.run(self.db,self.today,max_requests=4,clock=self.clock,sleep=self.clock.sleep,fetch=fetch,emit=lambda _:None)
        self.assertEqual(result,'limit')
        self.assertEqual(len(calls),4)
        self.assertEqual(calls[2][0],'/horse/100')
        self.assertEqual(calls[3][0],api.calendar_path('2026-09-30'))
        self.assertTrue(all(b[1]-a[1]>=30 for a,b in zip(calls,calls[1:])))
        count=self.db.execute('SELECT count(*) FROM requests').fetchone()[0]
        result=maintenance.run(self.db,self.today,max_requests=4,clock=self.clock,sleep=self.clock.sleep,
                               fetch=lambda _:api.Response(503,headers={'retry-after':'180'}),emit=lambda _:None)
        self.assertEqual(result,'retry')
        self.assertEqual(self.db.execute('SELECT count(*) FROM requests').fetchone()[0],count+1)
        self.assertEqual(self.db.execute('SELECT paused_until FROM control').fetchone()[0],self.clock()+180)

    def test_fresh_descendant_not_requeued_by_calendar_refresh(self):
        from test_collector import CALENDAR, DAY
        path=api.calendar_path(DAY)
        child=api.races_path(DAY,'H')
        with self.db:
            store.enqueue_refresh(self.db,path,'calendar',{'date':DAY},10,self.clock())
            store.enqueue(self.db,child,'races',{'date':DAY,'track':'H'})
            self.db.execute("UPDATE jobs SET status='done',last_success=? WHERE path=?",(self.clock(),child))
        calls=[]
        result=collector.run(self.db,queue='refresh',max_requests=4,clock=self.clock,sleep=self.clock.sleep,
                             fetch=lambda p:(calls.append(p) or response(CALENDAR)),emit=lambda _:None)
        self.assertEqual(result,'idle')
        self.assertEqual(calls,[path])
