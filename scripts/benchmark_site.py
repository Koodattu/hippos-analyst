"""Time all application routes on a populated deployment. Add --browser for rendered pages."""

import argparse
import gzip
import http.client
import json
import statistics
import time
from datetime import date, timedelta
from urllib.parse import urlencode, urlsplit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True)
    parser.add_argument('--today', required=True, type=date.fromisoformat)
    parser.add_argument('--repeat', type=int, default=3)
    parser.add_argument('--browser', action='store_true', help='Requires Playwright and Chromium')
    args = parser.parse_args()
    target = urlsplit(args.url)
    if target.scheme not in ('http','https') or not target.hostname or args.repeat < 1:
        parser.error('Provide an HTTP origin and a positive repetition count')
    connection = (http.client.HTTPSConnection if target.scheme=='https' else http.client.HTTPConnection)(
        target.hostname, target.port, timeout=60)

    def request(path):
        started = time.perf_counter()
        connection.request('GET',path,headers={'Accept-Encoding':'gzip'})
        response = connection.getresponse()
        body = response.read()
        if response.status != 200:
            raise RuntimeError(f'{path.split("?")[0]} returned HTTP {response.status}')
        if response.getheader('Content-Encoding') == 'gzip':
            body = gzip.decompress(body)
        if 'application/json' in response.getheader('Content-Type',''):
            body = json.loads(body)
        return body, (time.perf_counter()-started)*1000

    def path(name, params):
        query = urlencode(params, doseq=True)
        return '/api/'+name+('?' + query if query else '')

    def api(name, **params):
        return request(path(name,params))[0]

    today = args.today.isoformat()
    overview = api('overview')
    dates = {'from':(args.today-timedelta(days=30)).isoformat(),'to':today}
    all_dates = {'from':overview['first_date'],'to':today}
    calendar = api('calendar',**dates)
    meeting = next(m for m in reversed(calendar['meetings']) if any(r['entry_count'] for r in m['races']))
    race = dict(date=meeting['date'],track=meeting['track'],number=next(r['number'] for r in meeting['races'] if r['entry_count']))
    field = api('race',**race)['entries']
    horse = {'id':field[0]['horseId']}
    driver = {'role':'driver','id':next(e['driverId'] for e in field if e.get('driverId') not in (None,'','0'))}
    owner = {'role':'owner','id':api('parties',role='owner')['parties'][0]['id']}
    track = {'id':meeting['track_id'],'period':'history'}
    day = {'today':today}
    watch = dict(day, horse=horse['id'],driver=driver['id'])
    cases = [
        ('overview',{}),('calendar',dates),('calendar',all_dates),('coverage',{}),('meeting',race),('race',race),
        ('tracks',dict(day,all=1)),('track',dict(day,**track)),('horses',{}),('horse',horse),
        ('directory/horses',day),('directory/people',day),('people',{'role':'driver'}),('person',dict(driver,**{'from':today})),
        ('activity',dict(driver,**day)),('preview',dict(day,kind='driver',id=driver['id'])),
        ('parties',{'role':'owner'}),('party',owner),('saved',{'ids':horse['id'],'from':today}),('followed',watch),
        ('analytics',day),('analytics',dict(day,role='trainer',period='month')),('analytics',dict(day,role='driver',period='year')),
        ('predictions/results',dates),('predictions/results',all_dates),('predictions/results',dict(all_dates,mode='forecast')),
    ]

    def record(kind, name, samples):
        print(json.dumps(dict(kind=kind,route=name,median_ms=round(statistics.median(samples)),
                              min_ms=round(min(samples)),max_ms=round(max(samples)),samples=len(samples))), flush=True)

    try:
        for name,params in cases:
            label = name + (' '+params['period'] if 'period' in params else '')
            if name in ('calendar','predictions/results'):
                label += ' ' + params['from'] + ' ' + params.get('mode','')
            record('api',label,[request(path(name,params))[1] for _ in range(args.repeat)])
        record('http','healthz',[request('/healthz')[1] for _ in range(args.repeat)])
    finally:
        connection.close()
    if args.browser:
        from playwright.sync_api import sync_playwright
        pages = [('calendar',{}),('race',race),('meeting',race),('tracks',{}),('track',track),
                 ('horses',{}),('horse',horse),('horse',dict(horse,section='family')),('people',{}),
                 ('person',driver),('party',owner),('saved',{}),('coverage',{}),('analytics',{}),('predictions',{})]
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch()
            for name,params in pages:
                samples = []
                for _ in range(args.repeat):
                    page = browser.new_page()
                    errors = []
                    page.on('pageerror', lambda error: errors.append(str(error)))
                    page.on('response', lambda response: errors.append(str(response.status)) if response.status >= 400 else None)
                    if name == 'saved':
                        page.add_init_script("localStorage.setItem('hippos.saved-horses.v1',"+
                                             json.dumps(json.dumps([horse['id']]))+")")
                    page.add_init_script("""new MutationObserver((_,observer)=>{
                        const main=document.querySelector('#main:not([aria-busy])');
                        if(main?.querySelector('h1,h2')){performance.mark('content-ready');observer.disconnect()}
                    }).observe(document,{subtree:true,childList:true,attributes:true})""")
                    page.goto(args.url.rstrip('/')+'/#/'+name+'?'+urlencode(params))
                    page.locator('#main:not([aria-busy]) :is(h1,h2)').first.wait_for(timeout=60000)
                    if page.locator('#retry').count() or errors:
                        raise RuntimeError(f'{name} failed to render cleanly: {errors}')
                    if name == 'saved' and not page.locator('.watch-card').count():
                        raise RuntimeError('Saved list did not render the followed horse')
                    samples.append(page.evaluate("performance.getEntriesByName('content-ready')[0].startTime"))
                    page.close()
                record('page',name+' '+params.get('section',''),samples)
            browser.close()


if __name__ == '__main__':
    main()
