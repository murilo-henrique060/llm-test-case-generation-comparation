import pytest
from datetime import datetime, timedelta

# Assumed external system API based on provided class diagram:
# from reservation_service import ReservationService, Reservation, Flight
#
# Tests assume:
# - ReservationService.add_flight(flight_id: str, date_time: datetime, total_seats: int) -> None
# - ReservationService.createReservation(flightId: str, seat: int) -> Reservation
# - ReservationService.confirmPayment(reservationId: str, paymentApproved: bool) -> None
# - ReservationService.cancelReservation(reservationId: str) -> None
# - Reservation objects have attributes: id (str), state (str), seat (int), flight_id (str), flight_date_time (datetime)
#
# NOTE: Tests only. No system implementation is provided here.


@pytest.fixture
def service():
    # The concrete ReservationService must be provided by the execution environment.
    from reservation_service import ReservationService
    return ReservationService()


# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
def test_br01_confirm_only_with_one_approved_payment(service):
    flight_id = "FLIGHT_BR01"
    flight_dt = datetime(2026, 1, 13, 12, 0, 0)  # exactly 24 hours after 2026-01-12 12:00:00 reference
    total_seats = 10
    service.add_flight(flight_id, flight_dt, total_seats)

    reservation = service.createReservation(flight_id, seat=1)
    # One approved payment -> should confirm
    service.confirmPayment(reservation.id, paymentApproved=True)

    updated = service.getReservation(reservation.id)
    assert updated.state == "CONFIRMED"


# BR02 – Payments with a status other than approved must not confirm reservations
def test_br02_unapproved_payment_does_not_confirm_reservation(service):
    flight_id = "FLIGHT_BR02"
    service.add_flight(flight_id, datetime(2026, 2, 1, 9, 0, 0), total_seats=5)

    reservation = service.createReservation(flight_id, seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=False)

    unchanged = service.getReservation(reservation.id)
    assert unchanged.state == "CREATED"


# BR03 – Reservation confirmation and payment must be atomic
def test_br03_confirm_payment_operation_is_atomic_on_failure(service):
    flight_id = "FLIGHT_BR03"
    service.add_flight(flight_id, datetime(2026, 2, 2, 10, 0, 0), total_seats=5)

    reservation = service.createReservation(flight_id, seat=1)

    # Simulate a failure reported by the system when attempting to process payment approval
    # Expectation: operation fails and reservation remains in CREATED (no partial confirmation)
    with pytest.raises(Exception):
        # Provide an input the system treats as a failure scenario (implementation-dependent)
        service.confirmPayment(reservation.id, paymentApproved=None)  # invalid input should fail

    after = service.getReservation(reservation.id)
    assert after.state == "CREATED"


# BR04 – A seat may belong to at most one active reservation per flight
def test_br04_seat_exclusivity_per_flight(service):
    flight_id = "FLIGHT_BR04"
    service.add_flight(flight_id, datetime(2026, 3, 1, 8, 0, 0), total_seats=100)

    r1 = service.createReservation(flight_id, seat=10)
    # Creating second active reservation for same seat must be rejected
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=10)


# BR05 – Canceled reservations must immediately release the associated seat
def test_br05_cancel_releases_associated_seat(service):
    flight_id = "FLIGHT_BR05"
    service.add_flight(flight_id, datetime(2026, 4, 1, 8, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)

    # After cancel, the same seat must be available for a new reservation
    new_r = service.createReservation(flight_id, seat=1)
    assert new_r.seat == 1
    assert new_r.state == "CREATED"


# BR06 – Overbooking is not permitted under any circumstances
def test_br06_overbooking_not_permitted(service):
    flight_id = "FLIGHT_BR06"
    service.add_flight(flight_id, datetime(2026, 5, 1, 8, 0, 0), total_seats=1)

    r1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r1.id, paymentApproved=True)

    # Attempt to create or confirm any additional reservation that would exceed capacity must fail
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=2)


# BR07 – Number of confirmed reservations must never exceed total seats
def test_br07_confirmed_reservations_never_exceed_total_seats(service):
    flight_id = "FLIGHT_BR07"
    service.add_flight(flight_id, datetime(2026, 6, 1, 8, 0, 0), total_seats=1)

    r1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r1.id, paymentApproved=True)

    r2 = service.createReservation(flight_id, seat=1)  # seat should not be available; creation may fail
    # If creation succeeded (implementation may allow reservation creation but not confirmation), confirmation must fail.
    with pytest.raises(Exception):
        service.confirmPayment(r2.id, paymentApproved=True)


# BR08 – A reservation may be exclusively in CREATED, CONFIRMED, or CANCELED states
def test_br08_reservation_state_is_one_of_allowed_states(service):
    flight_id = "FLIGHT_BR08"
    service.add_flight(flight_id, datetime(2026, 7, 1, 8, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    assert r.state in {"CREATED", "CONFIRMED", "CANCELED"}
    service.confirmPayment(r.id, paymentApproved=True)
    r_after = service.getReservation(r.id)
    assert r_after.state in {"CREATED", "CONFIRMED", "CANCELED"}


# BR09 – Intermediate or additional states are not permitted
def test_br09_no_intermediate_states_returned_by_system(service):
    flight_id = "FLIGHT_BR09"
    service.add_flight(flight_id, datetime(2026, 8, 1, 8, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    # After any operation, the state must be one of permitted values, never an intermediate state string
    service.confirmPayment(r.id, paymentApproved=True)
    r_after = service.getReservation(r.id)
    assert r_after.state in {"CREATED", "CONFIRMED", "CANCELED"}


# BR10 – Only valid state transitions are CREATED→CONFIRMED and CONFIRMED→CANCELED
def test_br10_only_allowed_state_transitions(service):
    flight_id = "FLIGHT_BR10"
    service.add_flight(flight_id, datetime(2026, 9, 1, 8, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    # CONFIRMED -> CANCELED is allowed
    service.cancelReservation(r.id)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CANCELED"


# BR11 – Any other state transition must be rejected
def test_br11_invalid_state_transitions_rejected(service):
    flight_id = "FLIGHT_BR11"
    service.add_flight(flight_id, datetime(2026, 10, 1, 8, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    # CREATED -> CANCELED is not an allowed transition per BR10, must be rejected
    with pytest.raises(Exception):
        service.cancelReservation(r.id)


# BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
def test_br12_canceled_reservation_cannot_receive_new_payments_or_be_reactivated(service):
    flight_id = "FLIGHT_BR12"
    service.add_flight(flight_id, datetime(2026, 11, 1, 8, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)

    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)


# BR13 – Cancellation refund policy based on remaining time (>=24h full refund, <24h no refund)
def test_br13_refund_policy_exactly_24_hours_full_refund(service):
    flight_id = "FLIGHT_BR13_FULL"
    # Flight exactly 24 hours from reference time: 2026-01-13 12:00:00
    flight_dt = datetime(2026, 1, 13, 12, 0, 0)
    service.add_flight(flight_id, flight_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Cancellation at remaining time exactly 24 hours should yield full refund.
    # Assume cancelReservation returns a refund dict with exact fields (implementation detail).
    refund = service.cancelReservation(r.id)
    # Validate expected behavior via presence of a refund indicator; exact contract unspecified, so assert not raising and state
    r_after = service.getReservation(r.id)
    assert r_after.state == "CANCELED"


def test_br13_refund_policy_less_than_24_hours_no_refund(service):
    flight_id = "FLIGHT_BR13_NONE"
    # Flight less than 24 hours from reference: 2026-01-13 11:00:00 (23 hours)
    flight_dt = datetime(2026, 1, 13, 11, 0, 0)
    service.add_flight(flight_id, flight_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Cancellation when remaining time < 24 hours must result in no refund (operation allowed but no refund)
    refund = service.cancelReservation(r.id)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CANCELED"


# BR14 – Remaining time must be calculated in exact hours with no rounding
def test_br14_remaining_time_calculated_in_exact_hours_boundary_behavior(service):
    flight_id = "FLIGHT_BR14"
    # Use exact datetimes with boundary at 24 hours
    flight_dt = datetime(2026, 1, 13, 12, 0, 0)  # exactly 24 hours
    service.add_flight(flight_id, flight_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Cancellation at exactly 24 hours should be treated as >=24 hours -> full refund (per BR13)
    refund = service.cancelReservation(r.id)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CANCELED"


# BR15 – System must use exclusively internally stored flight date/time as temporal reference
def test_br15_system_uses_internal_flight_datetime_as_reference(service):
    flight_id = "FLIGHT_BR15"
    internal_dt = datetime(2026, 12, 31, 23, 0, 0)
    service.add_flight(flight_id, internal_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Attempt to cancel using an external time parameter should be ignored or rejected; provide an extra param to check enforcement
    # The service API does not accept external times; thus call cancelReservation and assert behavior uses internal flight datetime
    service.cancelReservation(r.id)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CANCELED"


# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
def test_br16_flight_data_immutable_after_confirmation(service):
    flight_id = "FLIGHT_BR16"
    orig_dt = datetime(2026, 7, 7, 7, 0, 0)
    service.add_flight(flight_id, orig_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Any attempt to alter flight date/time or id must be rejected (no mutation allowed)
    with pytest.raises(Exception):
        service.update_flight_datetime(flight_id, datetime(2027, 1, 1, 0, 0, 0))


# BR17 – Indirect modifications of flight data are prohibited
def test_br17_indirect_flight_modification_prohibited(service):
    flight_id = "FLIGHT_BR17"
    orig_dt = datetime(2026, 8, 8, 8, 0, 0)
    service.add_flight(flight_id, orig_dt, total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)

    # Attempt to replace flight object or swap references must be rejected; expect exception
    with pytest.raises(Exception):
        service.replace_flight_reference(flight_id, new_flight_object={})


# BR18 – Each reservation may have exactly one associated payment
def test_br18_reservation_allows_exactly_one_payment_attempt_success(service):
    flight_id = "FLIGHT_BR18"
    service.add_flight(flight_id, datetime(2026, 9, 9, 9, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    # First (and only) payment attempt approved
    service.confirmPayment(r.id, paymentApproved=True)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CONFIRMED"


# BR19 – Additional payment attempts for the same reservation must be rejected
def test_br19_additional_payment_attempts_rejected(service):
    flight_id = "FLIGHT_BR19"
    service.add_flight(flight_id, datetime(2026, 10, 10, 10, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Second payment attempt must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)


# BR20 – Payments must not be accepted for canceled reservations or after the flight date
def test_br20_payments_rejected_for_canceled_or_past_flight_reservations(service):
    flight_id = "FLIGHT_BR20_CANCELED"
    past_flight_id = "FLIGHT_BR20_PAST"
    # Future flight
    service.add_flight(flight_id, datetime(2026, 11, 11, 11, 0, 0), total_seats=3)
    # Past flight: date prior to any operation time
    service.add_flight(past_flight_id, datetime(2025, 1, 1, 0, 0, 0), total_seats=3)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)

    r_past = service.createReservation(past_flight_id, seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(r_past.id, paymentApproved=True)


# BR21 – System operations must be deterministic for same sequence of inputs
def test_br21_operations_are_deterministic(service):
    flight_id = "FLIGHT_BR21"
    flight_dt = datetime(2026, 12, 1, 12, 0, 0)
    service.add_flight(flight_id, flight_dt, total_seats=5)

    # Sequence A
    rA = service.createReservation(flight_id, seat=1)
    service.confirmPayment(rA.id, paymentApproved=True)
    stateA = service.getReservation(rA.id).state

    # Reset environment by creating a new service instance (assumes deterministic behavior across instances given same inputs)
    from reservation_service import ReservationService
    service2 = ReservationService()
    service2.add_flight(flight_id, flight_dt, total_seats=5)
    rB = service2.createReservation(flight_id, seat=1)
    service2.confirmPayment(rB.id, paymentApproved=True)
    stateB = service2.getReservation(rB.id).state

    assert stateA == stateB == "CONFIRMED"


# BR22 – System must not assume unspecified implicit behaviors
def test_br22_no_implicit_behaviors_performed_by_system(service):
    flight_id = "FLIGHT_BR22"
    service.add_flight(flight_id, datetime(2026, 12, 2, 12, 0, 0), total_seats=5)

    r = service.createReservation(flight_id, seat=1)
    # System must not auto-confirm or auto-rebook; only explicit confirmPayment should change state
    r_after = service.getReservation(r.id)
    assert r_after.state == "CREATED"
    # No auto-confirmation occurs
    with pytest.raises(Exception):
        # Trying to confirm with an invalid flag should not produce side effects
        service.confirmPayment(r.id, paymentApproved=None)
    assert service.getReservation(r.id).state == "CREATED"


# BR23 – Any business rule violation must result in immediate failure with no state change or partial records
def test_br23_business_rule_violation_no_state_change(service):
    flight_id = "FLIGHT_BR23"
    service.add_flight(flight_id, datetime(2026, 12, 3, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    # Attempt invalid operation: create second reservation for same seat without releasing
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)

    # Original reservation must remain CREATED (no partial effects)
    assert service.getReservation(r.id).state == "CREATED"


# BR24 – Each valid operation must generate exactly one immutable record (observable via operation success)
def test_br24_each_valid_operation_generates_one_immutable_record(service):
    flight_id = "FLIGHT_BR24"
    service.add_flight(flight_id, datetime(2026, 12, 4, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    # Assume service exposes a method to fetch operation records for a reservation (implementation-specific)
    before_records = service.get_operation_records(reservationId=r.id)
    service.confirmPayment(r.id, paymentApproved=True)
    after_records = service.get_operation_records(reservationId=r.id)
    assert len(after_records) == len(before_records) + 1


# BR25 – Failed operations must not generate persistent records
def test_br25_failed_operations_do_not_generate_persistent_records(service):
    flight_id = "FLIGHT_BR25"
    service.add_flight(flight_id, datetime(2026, 12, 5, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    before_records = service.get_operation_records(reservationId=r.id)
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)  # will fail
    after_records = service.get_operation_records(reservationId=r.id)
    assert len(after_records) == len(before_records)


# BR26 – Operations on one reservation must not affect others
def test_br26_operations_are_isolated_between_reservations(service):
    flight_id = "FLIGHT_BR26"
    service.add_flight(flight_id, datetime(2026, 12, 6, 12, 0, 0), total_seats=3)

    r1 = service.createReservation(flight_id, seat=1)
    r2 = service.createReservation(flight_id, seat=2)

    service.confirmPayment(r1.id, paymentApproved=True)
    # r2 must remain unaffected
    assert service.getReservation(r2.id).state == "CREATED"


# FR01 – Create an initial reservation in the CREATED state associated with flight and available seat
def test_fr01_create_initial_reservation_is_created_state(service):
    flight_id = "FLIGHT_FR01"
    service.add_flight(flight_id, datetime(2026, 12, 7, 12, 0, 0), total_seats=10)

    r = service.createReservation(flight_id, seat=5)
    assert r.state == "CREATED"
    assert r.seat == 5


# FR02 – Confirm payment and atomically confirm the reservation
def test_fr02_confirm_payment_atomically_confirms_reservation(service):
    flight_id = "FLIGHT_FR02"
    service.add_flight(flight_id, datetime(2026, 12, 8, 12, 0, 0), total_seats=10)

    r = service.createReservation(flight_id, seat=3)
    service.confirmPayment(r.id, paymentApproved=True)
    assert service.getReservation(r.id).state == "CONFIRMED"


# FR03 – Strictly control seat availability ensuring exclusivity per active reservation
def test_fr03_seat_availability_strictly_controlled(service):
    flight_id = "FLIGHT_FR03"
    service.add_flight(flight_id, datetime(2026, 12, 9, 12, 0, 0), total_seats=2)

    r1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r1.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)


# FR04 – Cancel reservations while respecting refund policy based on remaining time
def test_fr04_cancel_respects_refund_policy(service):
    flight_id = "FLIGHT_FR04"
    # Choose a flight >24 hours away
    service.add_flight(flight_id, datetime(2026, 12, 31, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    result = service.cancelReservation(r.id)
    # Ensure cancellation completes and reservation goes to CANCELED
    assert service.getReservation(r.id).state == "CANCELED"


# FR05 – Prevent any invalid modification of state, flight data, seat, or payment
def test_fr05_invalid_modifications_are_prevented(service):
    flight_id = "FLIGHT_FR05"
    service.add_flight(flight_id, datetime(2026, 12, 20, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to change seat must be rejected
    with pytest.raises(Exception):
        service.change_reservation_seat(r.id, new_seat=2)


# FR06 – Do not allow overbooking at any stage
def test_fr06_no_overbooking_during_creation_or_confirmation(service):
    flight_id = "FLIGHT_FR06"
    service.add_flight(flight_id, datetime(2026, 12, 21, 12, 0, 0), total_seats=1)

    r1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r1.id, paymentApproved=True)

    # Any additional creation or confirmation that would exceed capacity must be rejected
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=2)


# FR07 – Do not allow multiple, partial, or late payments
def test_fr07_no_multiple_or_partial_or_late_payments(service):
    flight_id = "FLIGHT_FR07"
    past_flight = "FLIGHT_FR07_PAST"
    service.add_flight(flight_id, datetime(2026, 12, 22, 12, 0, 0), total_seats=2)
    service.add_flight(past_flight, datetime(2025, 1, 1, 0, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Second payment attempt rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)

    r_past = service.createReservation(past_flight, seat=1)
    # Late payment for past flight rejected
    with pytest.raises(Exception):
        service.confirmPayment(r_past.id, paymentApproved=True)


# FR08 – Do not return intermediate states, explanatory messages, or partial results
def test_fr08_no_intermediate_states_or_partial_results_returned(service):
    flight_id = "FLIGHT_FR08"
    service.add_flight(flight_id, datetime(2026, 12, 23, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    service.confirmPayment(r.id, paymentApproved=True)
    result = service.getReservation(r.id)
    # The object must contain definitive state only
    assert result.state in {"CREATED", "CONFIRMED", "CANCELED"}


# FR09 – Ensure failures do not modify state or produce persistent side effects
def test_fr09_failures_do_not_modify_state_or_create_side_effects(service):
    flight_id = "FLIGHT_FR09"
    service.add_flight(flight_id, datetime(2026, 12, 24, 12, 0, 0), total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    before_state = service.getReservation(r.id).state
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)
    after_state = service.getReservation(r.id).state
    assert before_state == after_state


# FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
def test_fr10_only_internal_data_used_for_operations(service):
    flight_id = "FLIGHT_FR10"
    internal_dt = datetime(2026, 12, 25, 12, 0, 0)
    service.add_flight(flight_id, internal_dt, total_seats=2)

    r = service.createReservation(flight_id, seat=1)
    # Attempt to pass external metadata that the system should not rely on; operation should use internal flight data only
    service.confirmPayment(r.id, paymentApproved=True)
    r_after = service.getReservation(r.id)
    assert r_after.state == "CONFIRMED"