"""Idempotent seed: `python -m app.seed`.

Every seed complaint gets a deterministic UUID (uuid5 of its text), so running
the seed twice inserts nothing the second time. Seeds are triaged with
RuleBasedTriage — no LLM quota is spent on demo data.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from app.config import get_settings
from app.db import make_engine, make_session_factory
from app.domain import Status
from app.logging_setup import configure_logging
from app.models import Complaint
from app.providers.triage.rules import RuleBasedTriage
from app.repositories.complaint_repository import ComplaintRepository

log = logging.getLogger("civicpulse.seed")
SEED_NAMESPACE = uuid.UUID("6f1c1d2e-8a51-4c3e-9b1a-3c1f0c9e2b7a")

# (text, location, contact, status, hours_ago)
SEEDS: list[tuple[str, str, str | None, Status, int]] = [
    (
        "Burst water main flooding Street 12 since fajr, water entering ground floors of three houses.",
        "G-11/3 Street 12, Islamabad",
        "0300-1234567",
        Status.OPEN,
        2,
    ),
    (
        "Pani nahi aa raha for 3 days in our block, tanker mafia charging Rs 4000 per tanker.",
        "Block C, North Nazimabad, Karachi",
        None,
        Status.IN_PROGRESS,
        30,
    ),
    (
        "Bijli gone since 9 pm, transformer made loud blast and sparking near the masjid.",
        "Mohalla Qasimabad, Hyderabad",
        "0333-9876543",
        Status.OPEN,
        5,
    ),
    (
        "Gutter overflowing in front of school gate, children walking through sewage every morning.",
        "Samanabad main road, Lahore",
        None,
        Status.OPEN,
        8,
    ),
    (
        "Huge pothole on the sarak near Chandni Chowk, two bikes already fell last night.",
        "Murree Road, Chandni Chowk, Rawalpindi",
        "0312-5550001",
        Status.IN_PROGRESS,
        50,
    ),
    (
        "Streetlight outside house no 45 is not working for two weeks, street is very dark at night.",
        "F-7/2 Street 21, Islamabad",
        None,
        Status.RESOLVED,
        300,
    ),
    (
        "Kachra not picked up for one week, smell is unbearable and mosquitoes everywhere.",
        "Gulshan-e-Iqbal Block 13, Karachi",
        None,
        Status.OPEN,
        20,
    ),
    (
        "Load shedding 10 hours daily in our area even though schedule says 4 hours, please check.",
        "Satellite Town, Gujranwala",
        "0301-2223334",
        Status.OPEN,
        72,
    ),
    (
        "Water pipe leaking near the park since Eid, clean water wasting on road all day.",
        "Model Town Block H, Lahore",
        None,
        Status.RESOLVED,
        500,
    ),
    (
        "Open manhole without cover on main street, very dangerous for children and elderly people.",
        "Saddar, Peshawar",
        "0345-1112223",
        Status.IN_PROGRESS,
        12,
    ),
    (
        "Street light pole bent after storm and wires hanging low, please remove before accident.",
        "Bahria Town Phase 4, Rawalpindi",
        None,
        Status.OPEN,
        16,
    ),
    (
        "Sewer line choked, dirty water coming back into our washrooms, whole lane affected.",
        "Shah Faisal Colony, Karachi",
        "0321-4445556",
        Status.OPEN,
        6,
    ),
    (
        "Road construction left half finished for two months, dust everywhere and traffic jam daily.",
        "Canal Road near Thokar, Lahore",
        None,
        Status.REJECTED,
        900,
    ),
    (
        "Voltage fluctuation daily in evening, fridge and fan motors burnt in many houses.",
        "Gulberg III, Lahore",
        "0302-7778889",
        Status.OPEN,
        40,
    ),
    (
        "Garbage dump near the nala is on fire, black smoke entering houses, people coughing.",
        "Korangi Crossing, Karachi",
        None,
        Status.IN_PROGRESS,
        3,
    ),
    (
        "Tap water is coming yellow and smelly since yesterday, people falling ill in our street.",
        "Wahdat Colony, Faisalabad",
        "0306-3334445",
        Status.OPEN,
        10,
    ),
    (
        "Suggestion: please paint the faded zebra crossing near the girls college whenever possible.",
        "Jail Road, Lahore",
        None,
        Status.OPEN,
        120,
    ),
    (
        "Speed breaker too high near petrol pump, car bottoms getting damaged, request to fix it.",
        "University Road, Peshawar",
        None,
        Status.RESOLVED,
        700,
    ),
    (
        "Streetlights of whole block switched on in daytime and off at night, timer seems faulty.",
        "DHA Phase 2, Karachi",
        "0315-6667778",
        Status.OPEN,
        26,
    ),
    (
        "Electric meter reading wrong, bill came Rs 45000 for a two room house, need inspection.",
        "Johar Town Block R, Lahore",
        "0308-1231231",
        Status.IN_PROGRESS,
        96,
    ),
    (
        "Drain water standing in the street for 5 days after rain, dengue mosquitoes breeding.",
        "Shadman Colony, Multan",
        None,
        Status.OPEN,
        60,
    ),
    (
        "Main water supply line burst near the chowk, road flooded and shops closed.",
        "Liaquat Bazaar, Quetta",
        "0331-9090909",
        Status.OPEN,
        1,
    ),
    (
        "Cracks in the bridge railing on the canal, one portion already fell into water.",
        "Mall Road bridge, Lahore",
        None,
        Status.IN_PROGRESS,
        44,
    ),
    (
        "Live wire fell on the road after the storm, current in the puddle, danger for everyone.",
        "Hayatabad Phase 3, Peshawar",
        "0334-2020202",
        Status.OPEN,
        4,
    ),
    (
        "Park benches are broken and swings are rusty, kids cannot play, minor repair needed.",
        "F-9 Park, Islamabad",
        None,
        Status.OPEN,
        200,
    ),
    (
        "Sanitation staff not coming to our mohalla, people throwing trash on the empty plot.",
        "Lyari, Karachi",
        None,
        Status.REJECTED,
        400,
    ),
    (
        "No water for 5 days in the flats, old people carrying buckets from ground floor.",
        "Clifton Block 2, Karachi",
        "0322-5656565",
        Status.IN_PROGRESS,
        90,
    ),
    (
        "Transformer oil leaking and it is making buzzing noise, WAPDA line staff not responding.",
        "Madina Town, Faisalabad",
        None,
        Status.OPEN,
        18,
    ),
    (
        "Pothole filled with water near the hospital gate, ambulances slowing down, urgent please.",
        "Jinnah Hospital road, Lahore",
        "0304-8080808",
        Status.OPEN,
        7,
    ),
    (
        "Street light near the bus stop is flickering all night, women feel unsafe waiting there.",
        "I-8 Markaz, Islamabad",
        None,
        Status.RESOLVED,
        350,
    ),
    (
        "Stray dogs in large numbers near the school, children are scared to walk to class.",
        "Cantt area, Sialkot",
        None,
        Status.OPEN,
        36,
    ),
    (
        "Noise from marriage hall generator till 2 am every night, residents cannot sleep.",
        "Allama Iqbal Town, Lahore",
        "0311-4343434",
        Status.OPEN,
        55,
    ),
    (
        "Sewage mixing with drinking water line, whole street getting stomach problems.",
        "Orangi Town Sector 5, Karachi",
        "0317-2121212",
        Status.IN_PROGRESS,
        14,
    ),
    (
        "Footpath tiles broken and uneven in front of the market, an old man fell yesterday.",
        "Blue Area, Islamabad",
        None,
        Status.OPEN,
        22,
    ),
]


def seed_id(text: str) -> uuid.UUID:
    return uuid.uuid5(SEED_NAMESPACE, text)


def build_seed_complaints(now: datetime | None = None) -> list[Complaint]:
    now = now or datetime.now(UTC)
    rules = RuleBasedTriage()
    rows: list[Complaint] = []
    for i, (text, location, contact, status, hours_ago) in enumerate(SEEDS):
        result = rules.triage(text, location)
        created = now - timedelta(hours=hours_ago)
        rows.append(
            Complaint(
                id=seed_id(text),
                text=text,
                location=location,
                reporter_contact=contact,
                category=result.category,
                priority=result.priority,
                status=status,
                ai_summary=result.summary,
                triaged_by="rules",
                triage_latency_ms=1 + i % 3,
                created_at=created,
                updated_at=created,
            )
        )
    return rows


def run_seed(repo: ComplaintRepository) -> int:
    inserted = sum(repo.add_if_absent(c) for c in build_seed_complaints())
    repo.commit()
    return inserted


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    engine = make_engine(settings.database_url)
    session = make_session_factory(engine)()
    try:
        repo = ComplaintRepository(session)
        repo.lock_for_seed()  # concurrent init containers: one seeds, the others then find every row present
        inserted = run_seed(repo)
        log.info("seed complete", extra={"inserted": inserted, "total_seeds": len(SEEDS)})
    finally:
        session.close()
        engine.dispose()


if __name__ == "__main__":
    main()
