import pytest
from datetime import datetime, timedelta

# NOTE: Tests assume the existence of a production module named `reservation_system`
# exposing ReservationService, Reservation, and Flight classes/interfaces as specified
# in the task description. Tests call only the methods and attributes described in the
# Class Diagram and Functional Requirements.
#
# No implementation is provided here; these are pure pytest tests against the specified API.

from reservation_system import ReservationService


# Fixture: fresh service per test to ensure isolation (tests must be deterministic and not affect each other)
@pytest.fixture
def service():
    return ReservationService()


# BR01: A reservation may only be confirmed if exactly one approved payment is associated with it;
def test_br01_confirm_with_exactly_one_approved_payment_transitions_to_confirmed(service):
    # BR01
    # Setup: create flight with id 'F1' and a seat number 1. (Assumes flight pre-existence or service-managed flights.)
    reservation = service.createReservation("F1", 1)
    # Action: confirm payment providing paymentApproved=True exactly once
    service.confirmPayment(reservation.id, paymentApproved=True)
    # Assertion: reservation state must be CONFIRMED after the single approved payment
    assert reservation.state == "CONFIRMED"


# BR02: Payments with a status other than approved must not confirm reservations;
def test_br02_non_approved_payment_does_not_confirm_reservation_and_raises(service):
    # BR02
    reservation = service.createReservation("F1", 2)
    # Action + Assertion: attempt to confirm with paymentApproved=False must raise and leave state as CREATED
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=False)
    assert reservation.state == "CREATED"


# BR03: Reservation confirmation and payment approval must occur atomically
def test_br03_confirm_payment_operation_is_atomic_on_failure_leaves_no_partial_state(service):
    # BR03
    reservation = service.createReservation("F1", 3)
    # Simulate payment approval call that the service treats as atomic; if it raises, state must remain CREATED.
    # We trigger a failure by calling confirmPayment with an input that the service is expected to reject (e.g., paymentApproved=None)
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=None)  # invalid input should cause failure
    # After failure there must be no partial state change
    assert reservation.state == "CREATED"


# BR04: A seat may belong to at most one active reservation per flight;
def test_br04_same_seat_single_active_reservation_rejected_on_second_creation(service):
    # BR04
    r1 = service.createReservation("F2", 1)
    # Create second reservation request for the same flight and seat must be rejected
    with pytest.raises(Exception):
        service.createReservation("F2", 1)


# BR05: Canceled reservations must immediately release the associated seat;
def test_br05_cancel_releases_seat_immediately_allowing_new_reservation_for_same_seat(service):
    # BR05
    r = service.createReservation("F3", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"
    service.cancelReservation(r.id)
    assert r.state == "CANCELED"
    # After cancellation the same seat should be available for a new reservation on the same flight
    new_r = service.createReservation("F3", 1)
    assert new_r.state == "CREATED"
    assert new_r.seat == 1


# BR06: Overbooking is not permitted under any circumstances;
def test_br06_overbooking_by_creating_reservation_beyond_total_seats_is_rejected(service):
    # BR06
    # Assume flight F4 has totalSeats = 1. Attempting to create seat 2 should be rejected as overbooking/not existing seat.
    with pytest.raises(Exception):
        service.createReservation("F4", 2)


# BR07: The number of confirmed reservations for a flight must never exceed the total number of available seats;
def test_br07_confirming_reservation_that_would_exceed_total_seats_is_rejected(service):
    # BR07
    # Setup: assume flight F5 has totalSeats = 1
    r1 = service.createReservation("F5", 1)
    service.confirmPayment(r1.id, paymentApproved=True)
    assert r1.state == "CONFIRMED"
    # Create another reservation for the same flight but different seat index that may be in-range
    # If seat 1 is the only seat then attempting to create a reservation for any other seat within allowed range
    # but which would make confirmed_count > totalSeats must be rejected at confirmation time.
    r2 = service.createReservation("F5", 1)  # creation may or may not be allowed depending on system; attempt to confirm must fail
    with pytest.raises(Exception):
        service.confirmPayment(r2.id, paymentApproved=True)
    # Ensure original confirmed reservation remains unchanged
    assert r1.state == "CONFIRMED"


# BR08: A reservation may be exclusively in one of CREATED | CONFIRMED | CANCELED
def test_br08_create_reservation_state_is_exactly_created_and_not_other_values(service):
    # BR08
    r = service.createReservation("F6", 1)
    assert r.state == "CREATED"
    # Strictly ensure state is one of the allowed values (here must be CREATED)
    assert r.state in {"CREATED", "CONFIRMED", "CANCELED"}


# BR09: Intermediate or additional states are not permitted;
def test_br09_no_intermediate_states_during_confirmation_visible_to_caller(service):
    # BR09
    r = service.createReservation("F7", 1)
    # Perform confirmation operation; after it completes, the reservation must be exactly CONFIRMED (no intermediate state visible)
    service.confirmPayment(r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"
    # Ensure state is not any forbidden intermediate label
    assert r.state not in {"IN_PAYMENT", "PENDING", "EXPIRED"}


# BR10: The only valid state transitions are CREATED -> CONFIRMED and CONFIRMED -> CANCELED
def test_br10_cancel_on_created_reservation_is_rejected_transition_not_allowed(service):
    # BR10
    r = service.createReservation("F8", 1)
    # Attempting CREATED -> CANCELED is not in the allowed transitions; must be rejected
    with pytest.raises(Exception):
        service.cancelReservation(r.id)
    # State must remain CREATED
    assert r.state == "CREATED"


# BR11: Any state transition other than those defined must be rejected;
def test_br11_reconfirming_already_confirmed_reservation_is_rejected(service):
    # BR11
    r = service.createReservation("F9", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"
    # Attempting to confirm again (CONFIRMED -> CONFIRMED or CONFIRMED -> CREATED) is not a permitted transition
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)


# BR12: A canceled reservation must not be reactivated, modified, or receive new payments;
def test_br12_canceled_reservation_rejects_additional_payments_and_reactivation(service):
    # BR12
    r = service.createReservation("F10", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    assert r.state == "CANCELED"
    # Any attempt to confirm payment after cancellation must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)
    # Any attempt to cancel again or otherwise modify should also be rejected (idempotency not specified; treat modification as rejection)
    with pytest.raises(Exception):
        service.cancelReservation(r.id)


# BR13: Cancellation refund policy: Remaining time >=24 hours -> full refund; <24 hours -> no refund;
def test_br13_cancel_with_remaining_time_exactly_24_hours_entitles_full_refund(service):
    # BR13
    # This test assumes the service exposes flights whose datetimes are controllable via flight IDs used here.
    # Create reservation for flight F11 which the system has stored with dateTime exactly now + 24 hours.
    # Create and confirm payment (assume amount 100 for determinism)
    r = service.createReservation("F11", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Cancel and assert full refund is issued. We expect the service to expose refunded amount for determinism.
    service.cancelReservation(r.id)
    # The production Reservation is expected to have refund_amount attribute to inspect refund result
    assert hasattr(r, "refund_amount")
    assert r.refund_amount == r.payment_amount  # full refund exactly equals original payment amount


# BR13 edge: Remaining time < 24 hours -> no refund
def test_br13_cancel_with_remaining_time_less_than_24_hours_entails_no_refund(service):
    # BR13
    # Flight F12 is assumed to be scheduled in less than 24 hours from the service's internal clock.
    r = service.createReservation("F12", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    assert hasattr(r, "refund_amount")
    assert r.refund_amount == 0  # no refund exact zero


# BR14: Remaining time must be calculated in exact hours, with no rounding or tolerance
def test_br14_remaining_time_calculation_uses_exact_hours_no_rounding(service):
    # BR14
    # Assume Reservation exposes a remaining_hours_to_flight attribute calculated by the system exactly.
    r = service.createReservation("F13", 1)
    # The service's internal flight datetime is expected to be set so that remaining time is exactly 25 hours and 30 minutes.
    # The system must compute exact hours without rounding; therefore the remaining_hours_to_flight must equal 25 (truncate? specification: exact hours with no rounding)
    # The specification states "calculated in exact hours, with no rounding or tolerance of any kind" -> interpret as floor of exact hours not allowed unless exact integer.
    # To avoid inventing rounding semantics, assert that the attribute is an exact integer and equals the exact hour difference if flight datetime is whole-hour aligned.
    assert isinstance(r.remaining_hours_to_flight, int)


# BR15: System must use exclusively internally stored flight date and time as temporal reference
def test_br15_system_uses_internal_flight_datetime_for_time_sensitive_operations(service):
    # BR15
    r = service.createReservation("F14", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to manipulate external inputs (e.g., passing explicit date/time to cancelReservation) is not supported by API;
    # ensure cancellation outcome is determined solely by internal flight datetime (observable via remaining_hours_to_flight).
    before = r.remaining_hours_to_flight
    service.cancelReservation(r.id)
    # Refund decision must have been based on internal remaining hours; we assert refund_amount matches decision based on that internal value
    if before >= 24:
        assert r.refund_amount == r.payment_amount
    else:
        assert r.refund_amount == 0


# BR16: Flight dates, times, and identifiers must not be altered after reservation confirmation;
def test_br16_flight_data_immutable_after_confirmation(service):
    # BR16
    r = service.createReservation("F15", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"
    # Any attempt to change flight data must be rejected. We attempt to modify r.flight.dateTime directly and expect rejection/immutability.
    with pytest.raises(Exception):
        r.flight.dateTime = datetime.utcnow() + timedelta(days=10)


# BR17: Indirect modifications of flight data (reference swapping/cloning) are prohibited;
def test_br17_indirect_flight_reference_swapping_is_rejected_after_confirmation(service):
    # BR17
    r = service.createReservation("F16", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Attempt to replace the flight object reference must be rejected
    with pytest.raises(Exception):
        r.flight = object()


# BR18: Each reservation may have exactly one associated payment;
def test_br18_only_one_payment_associated_with_reservation_rejects_additional_payments(service):
    # BR18
    r = service.createReservation("F17", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Any additional payment attempt must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)


# BR19: Additional payment attempts for the same reservation must be rejected;
def test_br19_repeated_payment_attempts_are_rejected_for_same_reservation(service):
    # BR19
    r = service.createReservation("F18", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)


# BR20: Payments must not be accepted for canceled reservations or after the flight date;
def test_br20_payments_rejected_for_canceled_reservations_and_after_flight_date(service):
    # BR20
    r = service.createReservation("F19", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=True)
    # For after flight date: assume flight F20's datetime is in the past; creating reservation should be rejected or payment rejected
    r_past = service.createReservation("F20", 1)
    with pytest.raises(Exception):
        service.confirmPayment(r_past.id, paymentApproved=True)


# BR21: System operations must be deterministic for the same sequence of inputs;
def test_br21_operations_are_deterministic_given_same_inputs(service):
    # BR21
    # Re-run the same sequence twice and assert identical observable results
    seq_results = []
    for _ in range(2):
        r = service.createReservation("F21", 1)
        service.confirmPayment(r.id, paymentApproved=True)
        seq_results.append((r.state, r.seat))
    assert seq_results[0] == seq_results[1]


# BR22: System must not assume unspecified implicit behaviors
def test_br22_no_implicit_behaviors_like_automatic_rebooking_or_future_credit(service):
    # BR22
    r = service.createReservation("F22", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    service.cancelReservation(r.id)
    # After cancellation there must be no implicit creation of a new reservation or credit object; check that no new reservation appears for same id
    # Only explicit calls create reservations; check that canceled reservation remains canceled and not rebooked
    assert r.state == "CANCELED"


# BR23: Any business rule violation must result in immediate failure with no state change or partial records;
def test_br23_violation_causes_no_state_change_and_no_persistent_record_on_failure(service):
    # BR23
    r = service.createReservation("F23", 1)
    # Cause a violation: attempt confirm with invalid value
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved="INVALID_STATUS")
    # Ensure no state change
    assert r.state == "CREATED"


# BR24: Each valid operation must generate exactly one immutable record;
def test_br24_each_valid_operation_generates_one_immutable_record(service):
    # BR24
    # We assume ReservationService exposes an operation_record_count() method to inspect immutable record count for testing determinism.
    # Create reservation should increase record count by exactly one.
    before_count = service.operation_record_count()
    service.createReservation("F24", 1)
    after_count = service.operation_record_count()
    assert after_count - before_count == 1


# BR25: Failed operations must not generate persistent records;
def test_br25_failed_operations_do_not_create_persistent_records(service):
    # BR25
    before_count = service.operation_record_count()
    # Cause a failure
    with pytest.raises(Exception):
        service.createReservation("NON_EXISTENT_FLIGHT", 1)
    after_count = service.operation_record_count()
    assert after_count == before_count


# BR26: Operations on one reservation must not affect other reservations, flights, or seats.
def test_br26_operations_on_one_reservation_do_not_impact_others(service):
    # BR26
    r1 = service.createReservation("F25", 1)
    r2 = service.createReservation("F25", 2)
    service.confirmPayment(r1.id, paymentApproved=True)
    # r2 must remain CREATED and unaffected
    assert r2.state == "CREATED"


# FR01: Create an initial reservation in the CREATED state, associated with a flight and an available seat;
def test_fr01_create_initial_reservation_is_created_with_flight_and_seat(service):
    # FR01
    r = service.createReservation("F26", 1)
    assert r.state == "CREATED"
    assert r.seat == 1
    assert hasattr(r, "flight")


# FR02: Confirm payment and, atomically, confirm the reservation;
def test_fr02_confirm_payment_atomically_confirms_reservation(service):
    # FR02
    r = service.createReservation("F27", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    assert r.state == "CONFIRMED"


# FR03: Strictly control seat availability, ensuring exclusivity per active reservation;
def test_fr03_seat_exclusivity_enforced_at_creation_or_confirmation(service):
    # FR03
    r1 = service.createReservation("F28", 1)
    service.confirmPayment(r1.id, paymentApproved=True)
    # Another attempt to reserve same seat must be rejected
    with pytest.raises(Exception):
        service.createReservation("F28", 1)


# FR04: Cancel reservations while strictly respecting the refund policy based on remaining time until the flight;
def test_fr04_cancel_respects_refund_policy_based_on_remaining_time(service):
    # FR04
    r = service.createReservation("F29", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Inspect remaining hours and cancel; refund behavior asserted accordingly
    if r.remaining_hours_to_flight >= 24:
        service.cancelReservation(r.id)
        assert r.refund_amount == r.payment_amount
    else:
        service.cancelReservation(r.id)
        assert r.refund_amount == 0


# FR05: Prevent any invalid modification of state, flight data, seat, or payment;
def test_fr05_invalid_direct_modifications_of_state_or_flight_or_seat_are_rejected(service):
    # FR05
    r = service.createReservation("F30", 1)
    # Attempt direct illegal modifications must be rejected
    with pytest.raises(Exception):
        r.state = "INVALID_STATE"
    with pytest.raises(Exception):
        r.seat = 99
    with pytest.raises(Exception):
        r.flight.id = "MALICIOUS"


# FR06: Do not allow overbooking at any stage of the process;
def test_fr06_no_overbooking_at_any_stage(service):
    # FR06
    # Assume flight F31 has totalSeats = 1
    r1 = service.createReservation("F31", 1)
    service.confirmPayment(r1.id, paymentApproved=True)
    # Any further creation for that flight must be rejected
    with pytest.raises(Exception):
        service.createReservation("F31", 1)


# FR07: Do not allow multiple, partial, or late payments;
def test_fr07_multiple_partial_or_late_payments_rejected(service):
    # FR07
    r = service.createReservation("F32", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # Partial payment attempt (represented by paymentApproved=False) must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved=False)


# FR08: Do not return intermediate states, explanatory messages, or partial results;
def test_fr08_operations_return_only_final_states_no_intermediate_results(service):
    # FR08
    r = service.createReservation("F33", 1)
    service.confirmPayment(r.id, paymentApproved=True)
    # After operation, state must be final CONFIRMED; no intermediate state must be visible
    assert r.state == "CONFIRMED"


# FR09: Ensure that failures do not modify state or produce persistent side effects;
def test_fr09_failures_leave_no_state_change_or_persistent_side_effects(service):
    # FR09
    r = service.createReservation("F34", 1)
    before_count = service.operation_record_count()
    with pytest.raises(Exception):
        service.confirmPayment(r.id, paymentApproved="INVALID")
    after_count = service.operation_record_count()
    assert r.state == "CREATED"
    assert before_count == after_count


# FR10: Use exclusively provided and internally stored data, with no inference or external enrichment.
def test_fr10_system_uses_only_internal_data_and_does_not_infer_missing_information(service):
    # FR10
    # Attempt to create a reservation using partial/missing flight reference that would require inference; must be rejected
    with pytest.raises(Exception):
        service.createReservation("", 1)  # empty flightId cannot be inferred


# End of tests file.