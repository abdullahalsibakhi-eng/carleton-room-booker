import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from playwright.sync_api import sync_playwright, expect


BOOKING_URL = "https://carletonu.libcal.com/"
PREFERRED_ROOM = "421"
START_TIME = "14:30"
END_TIME = "17:30"

AVAILABLE_SLOT_SELECTOR = ".fc-timeline-event.s-lc-eq-avail"


def next_tuesday():
    today = datetime.now(ZoneInfo("America/Toronto")).date()
    days_ahead = (1 - today.weekday()) % 7 or 7
    return today + timedelta(days=days_ahead)


def select_booking_date(page, target_date):
    page.get_by_role("button", name="Go To Date").click()

    # Scope all actions to the open calendar.
    picker = page.locator(".datepicker:visible")
    expect(picker).to_be_visible(timeout=10000)

    days = picker.locator(".datepicker-days")
    expect(days).to_be_visible(timeout=10000)

    month_heading = target_date.strftime("%B %Y")
    heading = days.locator(".datepicker-switch")
    expect(heading).to_be_visible(timeout=10000)

    if heading.inner_text().strip() != month_heading:
        days.locator(".next").click()

    expect(heading).to_have_text(month_heading, timeout=10000)

    # Exclude dates from neighboring months.
    day = days.locator(
        "td.day:not(.old):not(.new):not(.disabled)"
    ).filter(has_text=re.compile(rf"^{target_date.day}$"))

    expect(day).to_have_count(1)
    day.click()

    expected_date = re.compile(
        rf"^{target_date:%A}, {target_date:%B} "
        rf"0?{target_date.day}, {target_date.year}$"
    )
    expect(page.get_by_text(expected_date)).to_be_visible(
        timeout=15000
    )

    print(f"Verified booking date: {target_date:%A, %B %d, %Y}")


def find_room_lane(page):
    resources = page.locator(".fc-datagrid-body [data-resource-id]")
    expect(resources.first).to_be_attached(timeout=15000)

    found_rooms = {}

    for resource in resources.all():
        room_id = resource.get_attribute("data-resource-id")
        name = " ".join(resource.inner_text().split())
        name = re.sub(r"^Info\s*", "", name).strip()

        if room_id and name:
            found_rooms[room_id] = name

    room_pattern = re.compile(
        rf"(?<!\w){re.escape(PREFERRED_ROOM)}(?!\w)"
    )

    matching_ids = [
        room_id
        for room_id, name in found_rooms.items()
        if room_pattern.search(name)
    ]

    if len(matching_ids) != 1:
        print("\nRoom labels found:")
        for room_id, name in found_rooms.items():
            print(f"  {room_id}: {name}")

        raise RuntimeError(
            f"Expected one match for room {PREFERRED_ROOM}, "
            f"but found {len(matching_ids)}."
        )

    room_id = matching_ids[0]
    matching_lanes = []

    for lane in page.locator(".fc-timeline-lane").all():
        lane_room_id = lane.evaluate(
            """el => {
                const owner = el.closest('[data-resource-id]');
                return owner
                    ? owner.getAttribute('data-resource-id')
                    : null;
            }"""
        )

        if lane_room_id == room_id:
            matching_lanes.append(lane)

    if len(matching_lanes) != 1:
        print(f"\nMatched room: {found_rooms[room_id]}")
        print(f"Resource ID: {room_id}")

        raise RuntimeError(
            f"Expected one timeline lane for room {PREFERRED_ROOM}, "
            f"but found {len(matching_lanes)}."
        )

    print(f"Found room {PREFERRED_ROOM}.")
    return matching_lanes[0]


def slot_column(page, slot_time):
    return page.locator(
        ".fc-timeline-slot-lane"
        f'[data-date="{slot_time:%Y-%m-%dT%H:%M:%S}"]'
    )


def available_event_at(page, lane, slot_time):
    column = slot_column(page, slot_time)
    expect(column).to_have_count(1)

    lane.scroll_into_view_if_needed()
    column.scroll_into_view_if_needed()

    column_box = column.bounding_box()
    if column_box is None:
        raise RuntimeError("Could not read the requested time column.")

    left = column_box["x"]
    right = left + column_box["width"]
    candidates = []

    for event in lane.locator(AVAILABLE_SLOT_SELECTOR).all():
        box = event.bounding_box()
        if box is None:
            continue

        if (
            box["x"] <= left + 3
            and box["x"] + box["width"] >= right - 3
        ):
            candidates.append(event)

    if len(candidates) != 1:
        raise RuntimeError(
            f"Room {PREFERRED_ROOM} is unavailable or could not be "
            f"verified at {slot_time:%H:%M}. Booking not prepared."
        )

    return candidates[0]


def find_available_rooms(page, target_date):
    start = datetime.fromisoformat(f"{target_date}T{START_TIME}:00")
    end = datetime.fromisoformat(f"{target_date}T{END_TIME}:00")

    if end <= start:
        raise ValueError("END_TIME must be later than START_TIME.")

    lane = find_room_lane(page)
    required_slots = []
    current = start

    while current < end:
        required_slots.append(current)
        current += timedelta(minutes=30)

    print(f"Checking {len(required_slots)} half-hour slots...")

    for slot_time in required_slots:
        available_event_at(page, lane, slot_time)
        print(f"  {slot_time:%H:%M}: available")

    return lane, start


def prepare_booking(page, target_date):
    lane, start = find_available_rooms(page, target_date)

    event = available_event_at(page, lane, start)
    column_box = slot_column(page, start).bounding_box()
    event_box = event.bounding_box()

    if column_box is None or event_box is None:
        raise RuntimeError(
            f"The calendar moved; could not locate {START_TIME}."
        )

    event.click(
        position={
            "x": (
                column_box["x"]
                + column_box["width"] / 2
                - event_box["x"]
            ),
            "y": event_box["height"] / 2,
        }
    )

    hour = start.hour % 12 or 12
    period = "am" if start.hour < 12 else "pm"

    start_label = re.compile(
        rf"^{re.escape(PREFERRED_ROOM)}:\s*"
        rf"{hour}:{start.minute:02d}\s*{period}\b",
        re.IGNORECASE,
    )

    end_dropdown = page.get_by_label(start_label)
    expect(end_dropdown).to_be_visible(timeout=15000)

    label_text = end_dropdown.evaluate(
        """el => Array.from(el.labels || [])
            .map(label => label.textContent)
            .join(' ')"""
    )

    expected_date = re.compile(
        rf"{target_date:%A},\s*{target_date:%B}\s+"
        rf"0?{target_date.day}\b",
        re.IGNORECASE,
    )

    if not expected_date.search(label_text):
        raise RuntimeError(
            "Could not verify the selected booking date. "
            f"Label: {label_text!r}"
        )

    end_value = f"{target_date} {END_TIME}:00"
    offered_option = end_dropdown.locator(
        f'option[value="{end_value}"]:not([disabled])'
    )

    try:
        expect(offered_option).to_have_count(1, timeout=10000)
    except AssertionError:
        offered = end_dropdown.locator("option").all_text_contents()

        raise RuntimeError(
            f"{END_TIME} is not offered. The selected start may still "
            "have a shorter default duration; the requested booking "
            "is NOT ready.\n"
            f"Offered ending times: {', '.join(offered)}"
        ) from None

    end_dropdown.select_option(value=end_value)
    expect(end_dropdown).to_have_value(end_value)

    print(
        f"\nPrepared: room {PREFERRED_ROOM}, {target_date}, "
        f"{START_TIME}–{END_TIME}."
    )
    print("Review the booking in the browser.")
    print("Submit Times has NOT been clicked.")


def main():
    target_date = next_tuesday()

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False)

        context = browser.new_context(
            timezone_id="America/Toronto",
            viewport={"width": 1440, "height": 1000},
        )

        page = context.new_page()
        page.set_default_timeout(15000)

        try:
            page.goto(BOOKING_URL, wait_until="domcontentloaded")

            page.get_by_role(
                "link",
                name=re.compile(
                    r"book study rooms on floors 2",
                    re.IGNORECASE,
                ),
            ).click()

            select_booking_date(page, target_date)
            prepare_booking(page, target_date)

        except Exception as exc:
            print(f"\nStopped: {exc}")
            print(
                "Nothing was submitted. "
                "Inspect the browser before continuing."
            )

        finally:
            try:
                input(
                    "\nThe browser is open for manual review. "
                    "Press Enter here ONLY when you want to close it..."
                )
            finally:
                context.close()
                browser.close()


if __name__ == "__main__":
    main()
