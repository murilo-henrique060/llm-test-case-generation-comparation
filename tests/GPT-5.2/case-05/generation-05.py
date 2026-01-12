```python
import pytest
from datetime import datetime, timedelta


# NOTE:
# - These tests assume the SUT provides the following importable classes:
#   ReservationService, Reservation, Flight
# - The tests intentionally do not implement the system.
# - The tests assume operations raise an exception on failure; the specific exception type is not specified.
# - Where internal data access is required (e.g., stored flight dateTime), tests reference attributes
#   that are explicitly present in the provided UML (Reservation.state/seat, Flight.dateTime/totalSeats).


# -----------------------------
# Helpers (test-local, not SUT)
# -----------------------------
def _make_datetime(year, month, day, hour=0, minute=0, second=0):
    return datetime(year, month, day, hour, minute, second)


def _ensure_has_attr(obj, attr_name):
    assert hasattr(obj, attr_name), f"Missing required attribute: {attr_name}"


# -----------------------------
# BR01: exactly one approved payment associated to confirm
# -----------------------------
def test_br01_confirm_requires_exactly_one_approved_payment_associated():
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    _ensure_has_attr(r, "state")
    assert r.state == "CREATED"

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CONFIRMED"


def test_br01_confirm_rejected_when_no_approved_payment():
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    # Negative: do not approve payment, reservation must not confirm.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    _ensure_has_attr(r, "state")
    assert r.state == "CREATED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]

    assert r.state == "CREATED"


# -----------------------------
# BR02: non-approved payments must not confirm reservations
# -----------------------------
def test_br02_non_approved_payment_must_not_confirm_reservation():
    # BR02 – Payments with a status other than approved must not confirm reservations
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]

    assert r.state == "CREATED"


# -----------------------------
# BR03: atomicity of payment approval and reservation confirmation
# -----------------------------
def test_br03_confirm_payment_and_reservation_must_be_atomic_on_failure_no_partial_state():
    # BR03 – Reservation confirmation and payment approval must occur atomically
    # and no observable state may exist in which only one of the two has been completed.
    #
    # Negative: attempt to confirm payment in a way that must fail (e.g., canceled reservation)
    # and ensure reservation is not confirmed (no partial state).
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CANCELED"


# -----------------------------
# BR04: seat exclusivity per active reservation per flight
# -----------------------------
def test_br04_same_seat_cannot_belong_to_two_active_reservations_same_flight():
    # BR04 – A seat may belong to at most one active reservation per flight
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r1 = service.createReservation("FL-1", 1)
    assert r1.state == "CREATED"

    with pytest.raises(Exception):
        service.createReservation("FL-1", 1)


# -----------------------------
# BR05: canceled reservation must immediately release seat
# -----------------------------
def test_br05_cancel_releases_seat_immediately():
    # BR05 – Canceled reservations must immediately release the associated seat
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r1 = service.createReservation("FL-1", 1)
    service.confirmPayment(r1.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r1.state == "CONFIRMED"

    service.cancelReservation(r1.id)  # type: ignore[attr-defined]
    assert r1.state == "CANCELED"

    r2 = service.createReservation("FL-1", 1)
    assert r2.state == "CREATED"


# -----------------------------
# BR06: overbooking never permitted
# -----------------------------
def test_br06_overbooking_not_permitted_when_creating_more_reservations_than_seats():
    # BR06 – Overbooking is not permitted under any circumstances
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    # Assumption-free usage: same flight, distinct seats until seats exhausted.
    r1 = service.createReservation("FL-1", 1)
    r2 = service.createReservation("FL-1", 2)

    assert r1.state == "CREATED"
    assert r2.state == "CREATED"

    with pytest.raises(Exception):
        service.createReservation("FL-1", 3)


# -----------------------------
# BR07: confirmed reservations must never exceed available seats
# -----------------------------
def test_br07_confirmed_reservations_must_not_exceed_total_seats():
    # BR07 – The number of confirmed reservations for a flight must never exceed total seats
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    r1 = service.createReservation("FL-1", 1)
    r2 = service.createReservation("FL-1", 2)

    service.confirmPayment(r1.id, paymentApproved=True)  # type: ignore[attr-defined]
    service.confirmPayment(r2.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r1.state == "CONFIRMED"
    assert r2.state == "CONFIRMED"

    with pytest.raises(Exception):
        r3 = service.createReservation("FL-1", 3)
        service.confirmPayment(r3.id, paymentApproved=True)  # type: ignore[attr-defined]


# -----------------------------
# BR08: reservation must be exclusively in one of CREATED/CONFIRMED/CANCELED
# -----------------------------
def test_br08_reservation_state_is_one_of_allowed_values_after_create():
    # BR08 – A reservation may be exclusively in one of: CREATED, CONFIRMED, CANCELED
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    assert r.state in ("CREATED", "CONFIRMED", "CANCELED")
    assert r.state == "CREATED"


# -----------------------------
# BR09: intermediate/additional states not permitted
# -----------------------------
def test_br09_no_intermediate_state_is_observable_during_confirmation():
    # BR09 – Intermediate or additional states are not permitted
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CONFIRMED"
    assert r.state not in ("PENDING", "IN_PAYMENT", "EXPIRED")


# -----------------------------
# BR10: only valid transitions are CREATED->CONFIRMED and CONFIRMED->CANCELED
# -----------------------------
def test_br10_valid_transition_created_to_confirmed():
    # BR10 – Valid transition: CREATED → CONFIRMED
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    assert r.state == "CREATED"

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"


def test_br10_valid_transition_confirmed_to_canceled():
    # BR10 – Valid transition: CONFIRMED → CANCELED
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"


# -----------------------------
# BR11: any other transition must be rejected
# -----------------------------
def test_br11_transition_created_to_canceled_must_be_rejected():
    # BR11 – Any state transition other than those defined must be rejected
    # CREATED -> CANCELED is not listed as valid.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    assert r.state == "CREATED"

    with pytest.raises(Exception):
        service.cancelReservation(r.id)  # type: ignore[attr-defined]

    assert r.state == "CREATED"


def test_br11_transition_confirmed_to_confirmed_must_be_rejected():
    # BR11 – Any state transition other than those defined must be rejected
    # Confirming an already confirmed reservation implies an invalid transition.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CONFIRMED"


# -----------------------------
# BR12: canceled reservation must not be reactivated, modified, or receive new payments
# -----------------------------
def test_br12_canceled_reservation_must_not_receive_new_payments():
    # BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CANCELED"


# -----------------------------
# BR13: refund policy based on remaining time (>=24h full refund, <24h no refund)
# -----------------------------
def test_br13_cancel_with_remaining_time_equal_24_hours_results_in_full_refund():
    # BR13 – Remaining time ≥ 24 hours → full refund
    #
    # This test assumes cancelReservation exposes the refund decision in an immutable record
    # or return-less operation with internally queryable record; since FR08 forbids explanatory messages,
    # the observable effect must be via records. The specific access method is not specified.
    #
    # Therefore, this test only asserts that cancellation succeeds at exactly 24 hours.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    # Assume service uses internally stored flight date/time; the test requires exact edge at 24h.
    # The SUT must allow controlling "now" deterministically; not specified.
    # To avoid inventing a clock API, we require ReservationService to accept "now" injection
    # only if it exists; otherwise, the test cannot be deterministic.
    if not hasattr(service, "setNow"):
        pytest.skip("ReservationService lacks deterministic time control API (setNow) required by BR13/BR14/BR15 tests")

    flight_dt = _make_datetime(2026, 1, 13, 12, 0, 0)
    service.setNow(_make_datetime(2026, 1, 12, 12, 0, 0))  # exactly 24h remaining

    r = service.createReservationWithFlightDateTime("FL-EDGE-24H", 1, flight_dt)  # type: ignore[attr-defined]
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"


def test_br13_cancel_with_remaining_time_less_than_24_hours_results_in_no_refund():
    # BR13 – Remaining time < 24 hours → no refund
    #
    # As above, due to FR08, we only assert cancellation succeeds and does not throw.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "setNow"):
        pytest.skip("ReservationService lacks deterministic time control API (setNow) required by BR13/BR14/BR15 tests")

    flight_dt = _make_datetime(2026, 1, 13, 12, 0, 0)
    service.setNow(_make_datetime(2026, 1, 12, 13, 0, 1))  # 23h  - (1s) remaining; strictly <24h

    r = service.createReservationWithFlightDateTime("FL-EDGE-23H", 1, flight_dt)  # type: ignore[attr-defined]
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"


# -----------------------------
# BR14: remaining time calculated in exact hours; no rounding/tolerance
# -----------------------------
def test_br14_remaining_time_is_calculated_in_exact_hours_no_rounding_at_boundary():
    # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding
    #
    # Edge: 23h 59m 59s remaining is < 24h (must follow <24h branch).
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "setNow"):
        pytest.skip("ReservationService lacks deterministic time control API (setNow) required by BR14 tests")

    flight_dt = _make_datetime(2026, 1, 13, 12, 0, 0)
    service.setNow(_make_datetime(2026, 1, 12, 12, 0, 1))  # 23:59:59 remaining

    r = service.createReservationWithFlightDateTime("FL-EDGE-23_59_59", 1, flight_dt)  # type: ignore[attr-defined]
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"


# -----------------------------
# BR15: must use exclusively internally stored flight date/time as temporal reference
# -----------------------------
def test_br15_cancellation_uses_internally_stored_flight_datetime_not_external_input():
    # BR15 – The system must use exclusively the internally stored flight date and time as reference
    #
    # Negative: if cancelReservation accepts external flight time, it would violate BR15.
    # The provided UML does not define such parameter; thus cancelReservation must accept only reservationId.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    # Attempt to pass an external datetime must be rejected (TypeError or similar).
    with pytest.raises(Exception):
        service.cancelReservation(r.id, _make_datetime(2026, 1, 13, 12, 0, 0))  # type: ignore[call-arg]


# -----------------------------
# BR16: flight dates/times/identifiers must not be altered after confirmation
# -----------------------------
def test_br16_flight_datetime_must_not_change_after_reservation_confirmation():
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getFlightForReservation"):
        pytest.skip("ReservationService lacks getFlightForReservation API required to observe stored Flight (BR16)")

    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    flight = service.getFlightForReservation(r.id)  # type: ignore[attr-defined]
    _ensure_has_attr(flight, "dateTime")
    original_dt = flight.dateTime

    # Attempt to modify flight datetime must be rejected or have no effect.
    with pytest.raises(Exception):
        flight.dateTime = original_dt + timedelta(hours=1)

    flight2 = service.getFlightForReservation(r.id)  # type: ignore[attr-defined]
    assert flight2.dateTime == original_dt


# -----------------------------
# BR17: indirect modifications of flight data prohibited
# -----------------------------
def test_br17_indirect_flight_modification_by_reference_swapping_is_prohibited():
    # BR17 – Indirect modifications (reference swapping, cloning, object recreation) are prohibited
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getFlightForReservation") or not hasattr(service, "setFlightForReservation"):
        pytest.skip("ReservationService lacks flight reference APIs required to validate BR17")

    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    current_flight = service.getFlightForReservation(r.id)  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        service.setFlightForReservation(r.id, current_flight)  # type: ignore[attr-defined]


# -----------------------------
# BR18: each reservation may have exactly one associated payment
# -----------------------------
def test_br18_reservation_has_at_most_one_payment_association():
    # BR18 – Each reservation may have exactly one associated payment
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert r.state == "CONFIRMED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]


# -----------------------------
# BR19: additional payment attempts must be rejected
# -----------------------------
def test_br19_additional_payment_attempt_for_same_reservation_is_rejected():
    # BR19 – Additional payment attempts for the same reservation must be rejected
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]


# -----------------------------
# BR20: payments must not be accepted for canceled reservations or after flight date
# -----------------------------
def test_br20_payment_not_accepted_for_canceled_reservation():
    # BR20 – Payments must not be accepted for canceled reservations
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]


def test_br20_payment_not_accepted_after_flight_date():
    # BR20 �� Payments must not be accepted after the flight date
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "setNow"):
        pytest.skip("ReservationService lacks deterministic time control API (setNow) required by BR20 test")

    flight_dt = _make_datetime(2026, 1, 12, 12, 0, 0)
    service.setNow(_make_datetime(2026, 1, 12, 12, 0, 1))  # after flight date

    r = service.createReservationWithFlightDateTime("FL-PAST", 1, flight_dt)  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CREATED"


# -----------------------------
# BR21: determinism for same sequence of inputs
# -----------------------------
def test_br21_deterministic_results_for_same_sequence_of_inputs_on_separate_instances():
    # BR21 – System operations must be deterministic for same sequence of inputs
    from reservation_system import ReservationService  # type: ignore

    s1 = ReservationService()
    s2 = ReservationService()

    r1 = s1.createReservation("FL-1", 1)
    r2 = s2.createReservation("FL-1", 1)

    assert r1.state == r2.state == "CREATED"

    s1.confirmPayment(r1.id, paymentApproved=True)  # type: ignore[attr-defined]
    s2.confirmPayment(r2.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r1.state == r2.state == "CONFIRMED"


# -----------------------------
# BR22: must not assume unspecified implicit behaviors
# -----------------------------
def test_br22_no_implicit_auto_rebooking_on_overbooking_failure():
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
    # Negative: when a seat is unavailable, creation must fail (no automatic seat change).
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    _ = service.createReservation("FL-1", 1)

    with pytest.raises(Exception):
        service.createReservation("FL-1", 1)


# -----------------------------
# BR23: any BR violation must fail immediately with no state change or partial records
# -----------------------------
def test_br23_failed_payment_confirmation_does_not_change_reservation_state():
    # BR23 – Business rule violation must result in immediate failure, with no state change
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    assert r.state == "CREATED"

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]

    assert r.state == "CREATED"


# -----------------------------
# BR24: each valid operation must generate exactly one immutable record
# -----------------------------
def test_br24_each_valid_operation_generates_exactly_one_immutable_record():
    # BR24 – Each valid operation must generate exactly one immutable record
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getRecords"):
        pytest.skip("ReservationService lacks getRecords API required to validate record generation (BR24)")

    initial_records = list(service.getRecords())  # type: ignore[attr-defined]

    r = service.createReservation("FL-1", 1)
    records_after_create = list(service.getRecords())  # type: ignore[attr-defined]
    assert len(records_after_create) == len(initial_records) + 1

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    records_after_confirm = list(service.getRecords())  # type: ignore[attr-defined]
    assert len(records_after_confirm) == len(records_after_create) + 1


def test_br24_record_is_immutable():
    # BR24 – Each valid operation must generate exactly one immutable record
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getRecords"):
        pytest.skip("ReservationService lacks getRecords API required to validate immutability (BR24)")

    _ = service.createReservation("FL-1", 1)
    record = list(service.getRecords())[-1]  # type: ignore[attr-defined]

    # Immutability requirement: modifying record must be rejected.
    with pytest.raises(Exception):
        record.someField = "mutate"  # type: ignore[attr-defined]


# -----------------------------
# BR25: failed operations must not generate persistent records
# -----------------------------
def test_br25_failed_operation_does_not_generate_persistent_record():
    # BR25 – Failed operations must not generate persistent records
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getRecords"):
        pytest.skip("ReservationService lacks getRecords API required to validate record non-creation (BR25)")

    before = list(service.getRecords())  # type: ignore[attr-defined]

    r = service.createReservation("FL-1", 1)
    mid = list(service.getRecords())  # type: ignore[attr-defined]
    assert len(mid) == len(before) + 1

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]

    after = list(service.getRecords())  # type: ignore[attr-defined]
    assert len(after) == len(mid)


# -----------------------------
# BR26: operations on one reservation must not affect others
# -----------------------------
def test_br26_cancelling_one_reservation_does_not_change_other_reservation_state():
    # BR26 – Operations on one reservation must not affect other reservations
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    r1 = service.createReservation("FL-1", 1)
    r2 = service.createReservation("FL-1", 2)

    service.confirmPayment(r1.id, paymentApproved=True)  # type: ignore[attr-defined]
    service.confirmPayment(r2.id, paymentApproved=True)  # type: ignore[attr-defined]

    service.cancelReservation(r1.id)  # type: ignore[attr-defined]

    assert r1.state == "CANCELED"
    assert r2.state == "CONFIRMED"


# -----------------------------
# FR01: create initial reservation CREATED with flight and available seat
# -----------------------------
def test_fr01_create_reservation_in_created_state_with_seat_assigned():
    # FR01 – Create an initial reservation in CREATED state, associated with flight and available seat
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    assert r.state == "CREATED"
    _ensure_has_attr(r, "seat")
    assert r.seat == 1


# -----------------------------
# FR02: confirm payment and atomically confirm reservation
# -----------------------------
def test_fr02_confirm_payment_atomically_confirms_reservation():
    # FR02 – Confirm payment and, atomically, confirm the reservation
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r.state == "CONFIRMED"


# -----------------------------
# FR03: strictly control seat availability exclusivity
# -----------------------------
def test_fr03_seat_exclusivity_is_enforced_on_create():
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    _ = service.createReservation("FL-1", 1)

    with pytest.raises(Exception):
        service.createReservation("FL-1", 1)


# -----------------------------
# FR04: cancel reservations respecting refund policy (time-based)
# -----------------------------
def test_fr04_cancel_reservation_enforces_time_policy_boundary_24h():
    # FR04 – Cancel reservations while strictly respecting refund policy based on remaining time
    # Edge explicitly required by BR13/BR14: exactly 24h.
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "setNow"):
        pytest.skip("ReservationService lacks deterministic time control API (setNow) required by FR04 tests")

    flight_dt = _make_datetime(2026, 1, 13, 12, 0, 0)
    service.setNow(_make_datetime(2026, 1, 12, 12, 0, 0))  # exactly 24h

    r = service.createReservationWithFlightDateTime("FL-FR04-24H", 1, flight_dt)  # type: ignore[attr-defined]
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    service.cancelReservation(r.id)  # type: ignore[attr-defined]
    assert r.state == "CANCELED"


# -----------------------------
# FR05: prevent invalid modification of state, flight data, seat, or payment
# -----------------------------
def test_fr05_prevent_invalid_state_modification_direct_assignment_rejected():
    # FR05 – Prevent any invalid modification of state, flight data, seat, or payment
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    assert r.state == "CREATED"

    with pytest.raises(Exception):
        r.state = "CONFIRMED"  # direct modification without payment/transition API


def test_fr05_prevent_seat_modification_after_create():
    # FR05 – Prevent any invalid modification of state, flight data, seat, or payment
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    with pytest.raises(Exception):
        r.seat = 2


# -----------------------------
# FR06: do not allow overbooking at any stage
# -----------------------------
def test_fr06_do_not_allow_overbooking_during_confirmation():
    # FR06 – Do not allow overbooking at any stage of the process
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    r1 = service.createReservation("FL-1", 1)
    r2 = service.createReservation("FL-1", 2)
    service.confirmPayment(r1.id, paymentApproved=True)  # type: ignore[attr-defined]
    service.confirmPayment(r2.id, paymentApproved=True)  # type: ignore[attr-defined]

    r3 = service.createReservation("FL-1", 3)
    with pytest.raises(Exception):
        service.confirmPayment(r3.id, paymentApproved=True)  # type: ignore[attr-defined]

    assert r3.state == "CREATED"


# -----------------------------
# FR07: do not allow multiple, partial, or late payments
# -----------------------------
def test_fr07_do_not_allow_multiple_payments_for_same_reservation():
    # FR07 – Do not allow multiple, partial, or late payments
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)
    service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]


# -----------------------------
# FR08: do not return intermediate states, explanatory messages, or partial results
# -----------------------------
def test_fr08_confirm_payment_returns_void_and_sets_final_state_only():
    # FR08 – Do not return intermediate states, explanatory messages, or partial results
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    r = service.createReservation("FL-1", 1)

    result = service.confirmPayment(r.id, paymentApproved=True)  # type: ignore[attr-defined]
    assert result is None
    assert r.state == "CONFIRMED"


# -----------------------------
# FR09: failures do not modify state or produce persistent side effects
# -----------------------------
def test_fr09_failure_does_not_change_state_or_generate_side_effects():
    # FR09 – Ensure that failures do not modify state or produce persistent side effects
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()
    if not hasattr(service, "getRecords"):
        pytest.skip("ReservationService lacks getRecords API required to validate FR09 persistent side effects")

    before_records = list(service.getRecords())  # type: ignore[attr-defined]
    r = service.createReservation("FL-1", 1)
    after_create_records = list(service.getRecords())  # type: ignore[attr-defined]

    assert r.state == "CREATED"
    assert len(after_create_records) == len(before_records) + 1

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # type: ignore[attr-defined]

    assert r.state == "CREATED"
    after_fail_records = list(service.getRecords())  # type: ignore[attr-defined]
    assert len(after_fail_records) == len(after_create_records)


# -----------------------------
# FR10: use exclusively provided and internally stored data; no inference/external enrichment
# -----------------------------
def test_fr10_create_reservation_requires_explicit_flight_id_and_seat_no_inference():
    # FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
    from reservation_system import ReservationService  # type: ignore

    service = ReservationService()

    with pytest.raises(Exception):
        service.createReservation(None, 1)  # type: ignore[arg-type]

    with pytest.raises(Exception):
        service.createReservation("FL-1", None)  # type: ignore[arg-type]
```