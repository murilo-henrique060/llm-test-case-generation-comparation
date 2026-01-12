```python
import pytest
from datetime import datetime, timedelta

# NOTE:
# These tests assume the existence of the following production classes (not implemented here):
# - ReservationService with methods:
#     createReservation(flightId: str, seat: int) -> Reservation
#     confirmPayment(reservationId: str, paymentApproved: bool) -> None
#     cancelReservation(reservationId: str) -> None
# - Reservation with attributes: state (CREATED|CONFIRMED|CANCELED), seat (int)
# - Flight with attributes: dateTime (datetime), totalSeats (int)
#
# The tests intentionally do NOT implement the system.


# -----------------------------
# Helpers (test-only)
# -----------------------------

def _make_flight_datetime_exact(hours_from_now: int) -> datetime:
    # Deterministic fixed "now" anchor (no external clock usage).
    # The system must use internally stored flight datetime (BR15), but tests need fixed values.
    base_now = datetime(2026, 1, 12, 12, 0, 0)
    return base_now + timedelta(hours=hours_from_now)


# -----------------------------
# FR01 / BR08 / BR09 / BR10 / BR11 / BR04 / BR06 / BR03 coverage requires a service fixture
# -----------------------------

@pytest.fixture
def service():
    # The SUT must be provided by the test environment.
    # Replace this fixture in your test suite to return a real ReservationService.
    raise NotImplementedError("Provide ReservationService instance via this fixture.")


@pytest.fixture
def flight_id():
    return "FL-001"


# -----------------------------
# BR01: Exactly one approved payment must be associated to confirm reservation
# -----------------------------

def test_br01_confirm_payment_approved_confirms_reservation_when_single_payment(service, flight_id):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert r.state == "CREATED"

    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    r2 = service.getReservation(reservationId=r.id)
    assert r2.state == "CONFIRMED"


def test_br01_confirm_payment_rejected_if_payment_already_exists_preventing_exactly_one(service, flight_id):
    # BR01 – Exactly one approved payment; second payment attempt must not be allowed (also BR18/BR19)
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)


# -----------------------------
# BR02: Non-approved payments must not confirm reservations
# -----------------------------

def test_br02_non_approved_payment_does_not_confirm_reservation(service, flight_id):
    # BR02 – Payments with a status other than approved must not confirm reservations
    r = service.createReservation(flight_id=flight_id, seat=1)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)

    r2 = service.getReservation(reservationId=r.id)
    assert r2.state == "CREATED"


# -----------------------------
# BR03: Payment approval and reservation confirmation must be atomic
# -----------------------------

def test_br03_failed_confirmation_does_not_leave_payment_approved_or_reservation_confirmed(service, flight_id):
    # BR03 – Reservation confirmation and payment approval must occur atomically
    # Scenario: force confirmPayment to fail due to seat already taken at confirm-time.
    r1 = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    assert service.getReservation(reservationId=r1.id).state == "CONFIRMED"

    r2 = service.createReservation(flight_id=flight_id, seat=1)  # created may be allowed; confirmation must fail

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    # No partial observable state: reservation must not be CONFIRMED, and payment must not be persisted/approved.
    r2_after = service.getReservation(reservationId=r2.id)
    assert r2_after.state == "CREATED"
    assert service.getPaymentForReservation(reservationId=r2.id) is None


# -----------------------------
# BR04: Seat exclusivity for at most one active reservation per flight
# -----------------------------

def test_br04_cannot_have_two_active_reservations_same_flight_same_seat(service, flight_id):
    # BR04 – A seat may belong to at most one active reservation per flight
    r1 = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    assert service.getReservation(reservationId=r1.id).state == "CONFIRMED"

    # Attempt to create another reservation for same flight+seat must be rejected (active reservation exists)
    with pytest.raises(Exception):
        service.createReservation(flight_id=flight_id, seat=1)


# -----------------------------
# BR05: Canceled reservations must immediately release the associated seat
# -----------------------------

def test_br05_cancel_immediately_releases_seat_for_new_reservation(service, flight_id):
    # BR05 – Canceled reservations must immediately release the associated seat
    r1 = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    assert service.getReservation(reservationId=r1.id).state == "CONFIRMED"

    service.cancelReservation(reservationId=r1.id)
    assert service.getReservation(reservationId=r1.id).state == "CANCELED"

    # Now seat must be available immediately
    r2 = service.createReservation(flight_id=flight_id, seat=1)
    assert r2.seat == 1
    assert r2.state == "CREATED"


# -----------------------------
# BR06: Overbooking not permitted under any circumstances
# -----------------------------

def test_br06_overbooking_not_permitted_when_total_seats_exhausted(service):
    # BR06 – Overbooking is not permitted under any circumstances
    flight = service.createFlight(flightId="FL-OVERBOOK-1", dateTime=_make_flight_datetime_exact(48), totalSeats=1)

    r1 = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    assert service.getReservation(reservationId=r1.id).state == "CONFIRMED"

    # No additional reservation can be created/confirmed beyond totalSeats=1
    with pytest.raises(Exception):
        service.createReservation(flightId=flight.id, seat=1)


# -----------------------------
# BR07: Confirmed reservations count must never exceed total seats
# -----------------------------

def test_br07_cannot_confirm_more_reservations_than_total_seats(service):
    # BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
    flight = service.createFlight(flightId="FL-CAP-1", dateTime=_make_flight_datetime_exact(48), totalSeats=1)

    r1 = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    assert service.getReservation(reservationId=r1.id).state == "CONFIRMED"

    r2 = service.createReservation(flightId=flight.id, seat=1)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    assert service.getReservation(reservationId=r2.id).state == "CREATED"
    assert service.countConfirmedReservations(flightId=flight.id) == 1


# -----------------------------
# BR08: Reservation must be exclusively in one of CREATED/CONFIRMED/CANCELED
# -----------------------------

def test_br08_reservation_state_is_one_of_the_three_allowed_states_after_creation(service, flight_id):
    # BR08 – A reservation may be exclusively in one of CREATED/CONFIRMED/CANCELED
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert r.state in ("CREATED", "CONFIRMED", "CANCELED")
    assert r.state == "CREATED"


# -----------------------------
# BR09: Intermediate/additional states are not permitted
# -----------------------------

def test_br09_confirm_payment_does_not_expose_intermediate_states(service, flight_id):
    # BR09 – Intermediate or additional states are not permitted
    r = service.createReservation(flight_id=flight_id, seat=1)

    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    # Only allowed states must be observable; specifically after confirm, must be CONFIRMED (no "pending" etc.)
    r2 = service.getReservation(reservationId=r.id)
    assert r2.state == "CONFIRMED"


# -----------------------------
# BR10: Only valid transitions are CREATED->CONFIRMED and CONFIRMED->CANCELED
# -----------------------------

def test_br10_created_to_confirmed_is_valid_transition(service, flight_id):
    # BR10 – Valid transition: CREATED → CONFIRMED
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert r.state == "CREATED"

    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    assert service.getReservation(reservationId=r.id).state == "CONFIRMED"


def test_br10_confirmed_to_canceled_is_valid_transition(service, flight_id):
    # BR10 – Valid transition: CONFIRMED → CANCELED
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert service.getReservation(reservationId=r.id).state == "CONFIRMED"

    service.cancelReservation(reservationId=r.id)
    assert service.getReservation(reservationId=r.id).state == "CANCELED"


# -----------------------------
# BR11: Any other transition must be rejected
# -----------------------------

def test_br11_created_to_canceled_transition_is_rejected(service, flight_id):
    # BR11 – Any state transition other than those defined must be rejected
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert service.getReservation(reservationId=r.id).state == "CREATED"

    with pytest.raises(Exception):
        service.cancelReservation(reservationId=r.id)

    assert service.getReservation(reservationId=r.id).state == "CREATED"


# -----------------------------
# BR12: Canceled reservation must not be reactivated, modified, or receive new payments
# -----------------------------

def test_br12_canceled_reservation_cannot_receive_new_payment(service, flight_id):
    # BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)
    assert service.getReservation(reservationId=r.id).state == "CANCELED"

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)

    assert service.getReservation(reservationId=r.id).state == "CANCELED"


# -----------------------------
# BR13: Refund policy based on remaining time >=24h full refund, <24h no refund
# -----------------------------

def test_br13_cancel_with_remaining_time_equal_24_hours_results_in_full_refund(service):
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund
    flight = service.createFlight(flightId="FL-REF-24", dateTime=_make_flight_datetime_exact(24), totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    service.cancelReservation(reservationId=r.id)

    refund = service.getRefundForReservation(reservationId=r.id)
    assert refund.type == "FULL"


def test_br13_cancel_with_remaining_time_less_than_24_hours_results_in_no_refund(service):
    # BR13 – Remaining time < 24 hours before the flight → no refund
    flight = service.createFlight(flightId="FL-REF-23", dateTime=_make_flight_datetime_exact(23), totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    service.cancelReservation(reservationId=r.id)

    refund = service.getRefundForReservation(reservationId=r.id)
    assert refund.type == "NONE"


# -----------------------------
# BR14: Remaining time must be calculated in exact hours, no rounding/tolerance
# -----------------------------

def test_br14_remaining_time_exact_hours_no_rounding_24h_minus_1_second_is_less_than_24(service):
    # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding or tolerance
    base_now = datetime(2026, 1, 12, 12, 0, 0)
    flight_dt = base_now + timedelta(hours=24) - timedelta(seconds=1)

    flight = service.createFlight(flightId="FL-EXACT-1", dateTime=flight_dt, totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    service.cancelReservation(reservationId=r.id)

    refund = service.getRefundForReservation(reservationId=r.id)
    assert refund.type == "NONE"


# -----------------------------
# BR15: Must use exclusively internally stored flight date/time as temporal reference
# -----------------------------

def test_br15_cancellation_refund_uses_internally_stored_flight_datetime_not_external_input(service):
    # BR15 – The system must use exclusively the internally stored flight date and time as the temporal reference
    # This test verifies cancelReservation takes no external datetime input and outcome depends only on stored flight dateTime.
    flight = service.createFlight(flightId="FL-INTERNAL-DT", dateTime=_make_flight_datetime_exact(23), totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    service.cancelReservation(reservationId=r.id)

    refund = service.getRefundForReservation(reservationId=r.id)
    assert refund.type == "NONE"


# -----------------------------
# BR16: Flight dates/times/identifiers must not be altered after reservation confirmation
# -----------------------------

def test_br16_attempt_to_modify_flight_datetime_after_confirmation_is_rejected(service):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    flight = service.createFlight(flightId="FL-IMM-1", dateTime=_make_flight_datetime_exact(48), totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.updateFlightDateTime(flightId=flight.id, newDateTime=_make_flight_datetime_exact(72))


# -----------------------------
# BR17: Indirect modifications of flight data prohibited (reference swapping/cloning/object recreation)
# -----------------------------

def test_br17_attempt_to_swap_flight_reference_on_confirmed_reservation_is_rejected(service):
    # BR17 – Indirect modifications of flight data (reference swapping, cloning, or object recreation) are prohibited
    flight1 = service.createFlight(flightId="FL-REF-1", dateTime=_make_flight_datetime_exact(48), totalSeats=1)
    flight2 = service.createFlight(flightId="FL-REF-2", dateTime=_make_flight_datetime_exact(48), totalSeats=1)

    r = service.createReservation(flightId=flight1.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert service.getReservation(reservationId=r.id).state == "CONFIRMED"

    with pytest.raises(Exception):
        service.reassignReservationFlight(reservationId=r.id, newFlightId=flight2.id)


# -----------------------------
# BR18: Each reservation may have exactly one associated payment
# -----------------------------

def test_br18_single_payment_association_exists_after_approved_confirmation(service, flight_id):
    # BR18 – Each reservation may have exactly one associated payment
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    payment = service.getPaymentForReservation(reservationId=r.id)
    assert payment is not None
    assert payment.reservationId == r.id


# -----------------------------
# BR19: Additional payment attempts for same reservation must be rejected
# -----------------------------

def test_br19_second_payment_attempt_is_rejected(service, flight_id):
    # BR19 – Additional payment attempts for the same reservation must be rejected
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)


# -----------------------------
# BR20: Payments must not be accepted for canceled reservations or after flight date
# -----------------------------

def test_br20_payment_not_accepted_for_canceled_reservation(service, flight_id):
    # BR20 – Payments must not be accepted for canceled reservations
    r = service.createReservation(flight_id=flight_id, seat=1)

    # Canceling CREATED is invalid (BR11), so confirm then cancel to reach canceled deterministically
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    service.cancelReservation(reservationId=r.id)
    assert service.getReservation(reservationId=r.id).state == "CANCELED"

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)


def test_br20_payment_not_accepted_after_flight_date(service):
    # BR20 – Payments must not be accepted after the flight date
    base_now = datetime(2026, 1, 12, 12, 0, 0)
    # Flight date is before "now" anchor by 1 hour
    flight_dt = base_now - timedelta(hours=1)

    flight = service.createFlight(flightId="FL-PAST-1", dateTime=flight_dt, totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)

    assert service.getReservation(reservationId=r.id).state == "CREATED"
    assert service.getPaymentForReservation(reservationId=r.id) is None


# -----------------------------
# BR21: Deterministic operations for same sequence of inputs
# -----------------------------

def test_br21_same_sequence_of_inputs_produces_same_result(service):
    # BR21 – System operations must be deterministic for the same sequence of inputs
    flight = service.createFlight(flightId="FL-DET-1", dateTime=_make_flight_datetime_exact(48), totalSeats=2)

    r1 = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.cancelReservation(reservationId=r1.id)

    r2 = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)
    service.cancelReservation(reservationId=r2.id)

    assert service.getReservation(reservationId=r1.id).state == "CANCELED"
    assert service.getReservation(reservationId=r2.id).state == "CANCELED"
    assert service.getRefundForReservation(reservationId=r1.id).type == service.getRefundForReservation(reservationId=r2.id).type


# -----------------------------
# BR22: Must not assume unspecified implicit behaviors
# -----------------------------

def test_br22_cancel_does_not_auto_rebook_or_create_additional_reservations(service, flight_id):
    # BR22 – The system must not assume unspecified implicit behaviors
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    before_count = service.countReservationsForFlight(flightId=r.flightId)

    service.cancelReservation(reservationId=r.id)

    after_count = service.countReservationsForFlight(flightId=r.flightId)
    assert after_count == before_count  # no auto-created reservations or rebooking side effects


# -----------------------------
# BR23: Any rule violation must fail immediately with no state change or partial records
# -----------------------------

def test_br23_on_business_rule_violation_no_state_change_and_no_partial_records(service, flight_id):
    # BR23 – Any business rule violation must result in immediate failure, with no state change or partial records
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert service.getReservation(reservationId=r.id).state == "CREATED"

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)

    assert service.getReservation(reservationId=r.id).state == "CREATED"
    assert service.getPaymentForReservation(reservationId=r.id) is None


# -----------------------------
# BR24: Each valid operation must generate exactly one immutable record
# -----------------------------

def test_br24_create_reservation_generates_exactly_one_immutable_record(service, flight_id):
    # BR24 – Each valid operation must generate exactly one immutable record
    before = service.countAuditRecords()

    r = service.createReservation(flight_id=flight_id, seat=1)

    after = service.countAuditRecords()
    assert after == before + 1

    record = service.getLatestAuditRecord()
    assert record.immutable is True
    assert record.operation == "createReservation"
    assert record.reservationId == r.id


def test_br24_confirm_payment_generates_exactly_one_immutable_record(service, flight_id):
    # BR24 – Each valid operation must generate exactly one immutable record
    r = service.createReservation(flight_id=flight_id, seat=1)

    before = service.countAuditRecords()
    service.confirmPayment(reservationId=r.id, paymentApproved=True)
    after = service.countAuditRecords()

    assert after == before + 1
    record = service.getLatestAuditRecord()
    assert record.immutable is True
    assert record.operation == "confirmPayment"
    assert record.reservationId == r.id


def test_br24_cancel_reservation_generates_exactly_one_immutable_record(service, flight_id):
    # BR24 – Each valid operation must generate exactly one immutable record
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    before = service.countAuditRecords()
    service.cancelReservation(reservationId=r.id)
    after = service.countAuditRecords()

    assert after == before + 1
    record = service.getLatestAuditRecord()
    assert record.immutable is True
    assert record.operation == "cancelReservation"
    assert record.reservationId == r.id


# -----------------------------
# BR25: Failed operations must not generate persistent records
# -----------------------------

def test_br25_failed_confirm_payment_does_not_generate_audit_record(service, flight_id):
    # BR25 – Failed operations must not generate persistent records
    r = service.createReservation(flight_id=flight_id, seat=1)

    before = service.countAuditRecords()
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=False)
    after = service.countAuditRecords()

    assert after == before


# -----------------------------
# BR26: Operations on one reservation must not affect other reservations/flights/seats
# -----------------------------

def test_br26_cancel_one_reservation_does_not_change_other_reservation_state(service):
    # BR26 – Operations performed on one reservation must not affect other reservations, flights, or seats
    flight = service.createFlight(flightId="FL-ISO-1", dateTime=_make_flight_datetime_exact(48), totalSeats=2)

    r1 = service.createReservation(flightId=flight.id, seat=1)
    r2 = service.createReservation(flightId=flight.id, seat=2)

    service.confirmPayment(reservationId=r1.id, paymentApproved=True)
    service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    service.cancelReservation(reservationId=r1.id)

    assert service.getReservation(reservationId=r1.id).state == "CANCELED"
    assert service.getReservation(reservationId=r2.id).state == "CONFIRMED"


# -----------------------------
# FR01: Create initial reservation in CREATED state associated with flight and available seat
# -----------------------------

def test_fr01_create_reservation_returns_created_state_with_flight_and_seat(service, flight_id):
    # FR01 – Create an initial reservation in the CREATED state, associated with a flight and an available seat
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert r.state == "CREATED"
    assert r.seat == 1
    assert r.flightId == flight_id


# -----------------------------
# FR02: Confirm payment and atomically confirm reservation
# -----------------------------

def test_fr02_confirm_payment_confirms_reservation_atomically(service, flight_id):
    # FR02 – Confirm payment and, atomically, confirm the reservation
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    assert service.getReservation(reservationId=r.id).state == "CONFIRMED"
    payment = service.getPaymentForReservation(reservationId=r.id)
    assert payment is not None
    assert payment.status == "APPROVED"


# -----------------------------
# FR03: Strictly control seat availability, exclusivity per active reservation
# -----------------------------

def test_fr03_seat_exclusivity_prevents_second_active_reservation(service, flight_id):
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    r1 = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.createReservation(flight_id=flight_id, seat=1)


# -----------------------------
# FR04: Cancel reservations respecting refund policy based on remaining time
# -----------------------------

def test_fr04_cancel_applies_full_refund_when_remaining_time_is_24_hours(service):
    # FR04 – Cancel reservations while strictly respecting the refund policy based on remaining time until the flight
    flight = service.createFlight(flightId="FL-FR04-1", dateTime=_make_flight_datetime_exact(24), totalSeats=1)
    r = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    service.cancelReservation(reservationId=r.id)

    assert service.getReservation(reservationId=r.id).state == "CANCELED"
    assert service.getRefundForReservation(reservationId=r.id).type == "FULL"


# -----------------------------
# FR05: Prevent invalid modification of state, flight data, seat, or payment
# -----------------------------

def test_fr05_attempt_to_change_seat_after_confirmation_is_rejected(service, flight_id):
    # FR05 – Prevent any invalid modification of state, flight data, seat, or payment
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.changeReservationSeat(reservationId=r.id, newSeat=2)


# -----------------------------
# FR06: Do not allow overbooking at any stage
# -----------------------------

def test_fr06_cannot_confirm_if_would_overbook(service):
    # FR06 – Do not allow overbooking at any stage of the process
    flight = service.createFlight(flightId="FL-FR06-1", dateTime=_make_flight_datetime_exact(48), totalSeats=1)

    r1 = service.createReservation(flightId=flight.id, seat=1)
    service.confirmPayment(reservationId=r1.id, paymentApproved=True)

    r2 = service.createReservation(flightId=flight.id, seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r2.id, paymentApproved=True)

    assert service.countConfirmedReservations(flightId=flight.id) == 1


# -----------------------------
# FR07: Do not allow multiple, partial, or late payments
# -----------------------------

def test_fr07_multiple_payments_for_same_reservation_are_rejected(service, flight_id):
    # FR07 – Do not allow multiple, partial, or late payments
    r = service.createReservation(flight_id=flight_id, seat=1)
    service.confirmPayment(reservationId=r.id, paymentApproved=True)

    with pytest.raises(Exception):
        service.confirmPayment(reservationId=r.id, paymentApproved=True)


# -----------------------------
# FR08: Do not return intermediate states, explanatory messages, or partial results
# -----------------------------

def test_fr08_confirm_payment_returns_no_partial_result(service, flight_id):
    # FR08 – Do not return intermediate states, explanatory messages, or partial results
    r = service.createReservation(flight_id=flight_id, seat=1)

    result = service.confirmPayment(reservationId=r.id, paymentApproved=True)
    assert result is None


# -----------------------------
# FR09: Failures do not modify state or produce persistent side effects
# -----------------------------

def test_fr09_failed_cancel_does_not_change_state_or_create_records(service, flight_id):
    # FR09 – Ensure that failures do not modify state or produce persistent side effects
    r = service.createReservation(flight_id=flight_id, seat=1)
    assert service.getReservation(reservationId=r.id).state == "CREATED"

    before_records = service.countAuditRecords()
    with pytest.raises(Exception):
        service.cancelReservation(reservationId=r.id)  # invalid transition CREATED->CANCELED (BR11)
    after_records = service.countAuditRecords()

    assert service.getReservation(reservationId=r.id).state == "CREATED"
    assert after_records == before_records


# -----------------------------
# FR10: Use exclusively provided and internally stored data; no inference/external enrichment
# -----------------------------

def test_fr10_create_reservation_requires_explicit_flight_id_and_seat(service):
    # FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
    with pytest.raises(Exception):
        service.createReservation(flight_id=None, seat=1)

    with pytest.raises(Exception):
        service.createReservation(flight_id="FL-EXPLICIT-REQ", seat=None)
```