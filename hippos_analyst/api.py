"""The observed, public Hippos racing API. No login or browser session."""

import json
import re
import socket
from dataclasses import dataclass
from datetime import date
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

BASE_URL = "https://heppa.hippos.fi/heppa2_backend"
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class SchemaError(ValueError):
    """A response cannot safely be interpreted using the observed contract."""


def iso_date(value):
    if not isinstance(value, str) or date.fromisoformat(value).isoformat() != value:
        raise ValueError("Expected a date in YYYY-MM-DD format")
    return value


def identifier(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise SchemaError('Invalid track or race identifier type')
    value = str(value)
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise SchemaError("Invalid track or race identifier")
    return value


def calendar_path(day):
    return f"/race/search/{iso_date(day)}/{day}/"


def races_path(day, track):
    return f"/race/{iso_date(day)}/{identifier(track)}/races"


def runners_path(day, track, number):
    return f"/race/{iso_date(day)}/{identifier(track)}/start/{identifier(number)}"


@dataclass
class Response:
    status: int
    body: bytes = b""
    headers: dict | None = None

    def json(self):
        content_type = (self.headers or {}).get("content-type", "").split(";")[0].strip()
        if content_type != "application/json":
            raise SchemaError("Expected application/json")
        try:
            return json.loads(self.body)
        except (ValueError, UnicodeError) as exc:
            raise SchemaError("Response is not valid JSON") from exc


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(path):
    # Paths are derived from validated calendar records, never arbitrary URLs.
    if not re.fullmatch(r"/race/(?:search/\d{4}-\d{2}-\d{2}/\d{4}-\d{2}-\d{2}/|"
                        r"\d{4}-\d{2}-\d{2}/[A-Za-z0-9_-]+/(?:races|start/[A-Za-z0-9_-]+))", path):
        raise ValueError("Unsupported Hippos API path")
    request = Request(BASE_URL + path, headers={
        "Accept": "application/json",
        "User-Agent": "hippos-analyst/0.1 (private educational research; single worker)",
    })
    try:
        with build_opener(NoRedirects()).open(request, timeout=30) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                raise SchemaError("Response exceeds the 8 MiB limit")
            return Response(response.status, body, {k.lower(): v for k, v in response.headers.items()})
    except HTTPError as exc:
        # Error pages and session headers are not archived.
        with exc:
            return Response(exc.code, headers={k.lower(): v for k, v in exc.headers.items()})
    except (URLError, TimeoutError, socket.timeout, OSError, HTTPException):
        return Response(0)


MEETING_FIELDS = "date trackCode startTime name eventType trackShortname trackType trackNumber meetNumber trackCondition temperature trackCity trackName canceled hasPublishedResults isFreeToPublish majorRace finnishTrack latitude longitude formattedTrackName".split()
RACE_FIELDS = "date trackCode startNumber categoryNumber plannedTime actualTime startType startForm monte totoResultsReady publishFree eventType baseDistance finnishTrack trackNumber firstPrice priceSum status specialRace".split()
RUNNER_FIELDS = "date trackCode startNumber startForm monte programNumber lane distance placing totalTime kilometerTime shortKilometerTime price winOdds winOddsStr horseId horseName horseBreed horseRegistrationCountry trainerId trainerName driverId driverName gallop absent shoesFront shoesBack americanSulkyKEX startType testStartAccepted finnishTrack trackNumber horsePriceSum record recordType recordMonte status startAmount condition expectedValue trainerCommentsUpdated distanceCode shortCarRecord shortRecord".split()
BOOLEAN_FIELDS = frozenset('absent canceled hasPublishedResults monte finnishTrack totoResultsReady publishFree isFreeToPublish gallop'.split())


def selected(record, fields):
    if not isinstance(record, dict):
        raise SchemaError("Expected a record object")
    result = {}
    for key in fields:
        if key in record:
            value = record[key]
            if key in BOOLEAN_FIELDS and not isinstance(value, bool):
                raise SchemaError(f'Expected a boolean for {key}')
            if value is not None and not isinstance(value, (str, bool, int, float)):
                raise SchemaError(f"Unexpected structure for {key}")
            result[key] = value
    return result


def identity(record, day, track=None, number=None):
    if record.get("date") != day:
        raise SchemaError("Record date does not match the requested day")
    if track is not None and record.get("trackCode") != track:
        raise SchemaError("Record track does not match the requested meeting")
    if number is not None and str(record.get("startNumber")) != str(number):
        raise SchemaError("Record race does not match the requested race")


def normalize(kind, payload, context):
    """Validate complete responses and retain only research-relevant fields."""
    if not isinstance(payload, list):
        raise SchemaError("Expected an array, not an error object or another schema")
    day = context["date"]
    output = []
    seen = set()
    for item in payload:
        if not isinstance(item, dict):
            raise SchemaError("Expected record objects")
        if kind == "calendar":
            if item.get("raceDate") != day or not isinstance(item.get("events"), list):
                raise SchemaError("Unexpected calendar structure")
            for event in item["events"]:
                record = selected(event, MEETING_FIELDS)
                identity(record, day)
                if not isinstance(record.get("finnishTrack"), bool):
                    raise SchemaError("Missing Finnish-track indicator")
                if not record["finnishTrack"]:
                    continue
                track = record.get("trackCode")
                if not isinstance(track, str):
                    raise SchemaError("Missing track code")
                identifier(track)
                if track in seen:
                    raise SchemaError("Duplicate meeting in calendar")
                seen.add(track)
                output.append(record)
        elif kind == "races":
            record = selected(item.get("race"), RACE_FIELDS)
            identity(record, day, context["track"])
            if record.get("startNumber") is None:
                raise SchemaError("Missing race number")
            record["startNumber"] = identifier(record["startNumber"])
            if record["startNumber"] in seen:
                raise SchemaError("Duplicate race number")
            seen.add(record["startNumber"])
            output.append(record)
        elif kind == "runners":
            record = selected(item, RUNNER_FIELDS)
            if 'absent' not in record:
                raise SchemaError('Missing scratch indicator')
            record['startNumber'] = identifier(record.get('startNumber'))
            identity(record, day, context["track"], context["number"])
            horse_id = record.get("horseId")
            if isinstance(horse_id, bool) or not isinstance(horse_id, (str, int)) or not re.fullmatch(r"\d+", str(horse_id)):
                raise SchemaError("Missing or invalid horse ID")
            record["horseId"] = str(horse_id)
            program = record.get('programNumber')
            if isinstance(program, bool) or not isinstance(program, (str, int)) or not re.fullmatch(r'\d+', str(program)):
                raise SchemaError('Missing or invalid participant number')
            if not isinstance(record.get("horseName"), str):
                raise SchemaError("Missing participant number or horse name")
            record["programNumber"] = str(record["programNumber"])
            if record["programNumber"] in seen:
                raise SchemaError("Duplicate participant number")
            seen.add(record["programNumber"])
            for key in ("driverId", "trainerId"):
                if record.get(key) is not None:
                    record[key] = str(record[key])
            output.append(record)
        else:
            raise SchemaError("Unknown job kind")
    return output
