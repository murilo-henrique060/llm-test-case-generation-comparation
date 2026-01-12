```python
# tests_reservation_system.py
# Generated pytest test suite validating Business Rules (BR) and Functional Requirements (FR)
# All tests assume the presence of a ReservationService implementing the public API described
# in the provided specification:
# - ReservationService.createReservation(flightId: str, seat: int) -> Reservation
# - ReservationService.confirmPayment(reservationId: str, paymentApproved: bool) -> None
# - ReservationService.cancelReservation(reservationId: str) -> None
# - Flight is referenced by flightId used when creating reservations
# The tests use only pytest and standard library modules.

import datetime
import pytest

# The system under test is expected to be provided externally.
# The tests below reference a symbol ReservationService from the production code.
# Replace the import below with the actual module path when running tests.
from reservation_service import ReservationService

# Utility fixed datetimes for deterministic tests
DT_NOW = datetime.datetime(2026, 1, 12, 10, 0, 0)
DT_25_HOURS = datetime.datetime(2026, 1, 13, 11, 0, 0)   # 25 hours after DT_NOW
DT_23_HOURS = datetime.datetime(2026, 1, 13, 9, 0, 0)    # 23 hours after DT_NOW
DT_PAST = datetime.datetime(2026, 1, 11, 10, 0, 0)       # before DT_NOW


@pytest.fixture
def service():
    # Each test receives a fresh ReservationService instance to ensure isolation (BR26, BR21).
    # The service is expected to be deterministic.
    svc = ReservationService()
    return svc


# FR01 – Create an initial reservation in the CREATED state, associated with a flight and an available seat
def test_create_reservation_returns_created_state_and_assigns_seat(service):
    # FR01
    flight_id = "FL-CR-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=10)
    reservation = service.createReservation(flight_id, seat=1)
    assert reservation.state == "CREATED"
    assert reservation.seat == 1
    assert reservation.flight_id == flight_id


# BR08 – A reservation may be exclusively in one of the following states: CREATED, CONFIRMED, CANCELED
def test_reservation_initial_state_is_one_of_allowed_states_only(service):
    # BR08
    flight_id = "FL-BR08-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=1)
    assert reservation.state in {"CREATED", "CONFIRMED", "CANCELED"}
    # Newly created reservation must be exactly CREATED
    assert reservation.state == "CREATED"


# BR10 – Only valid state transitions are CREATED → CONFIRMED and CONFIRMED → CANCELED
def test_invalid_state_transition_from_created_to_created_is_rejected(service):
    # BR10
    flight_id = "FL-BR10-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=1)
    # Attempting to 'transition' to CREATED again is not a defined transition; expect failure
    with pytest.raises(Exception):
        service._force_set_state(reservation.id, "CREATED")  # Assume system prohibits invalid transition


# BR11 – Any state transition other than those defined must be rejected
def test_direct_transition_from_created_to_canceled_is_rejected_without_confirm(service):
    # BR11
    flight_id = "FL-BR11-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=2)
    # Directly changing state to CANCELED without going through CONFIRMED must be rejected
    with pytest.raises(Exception):
        service._force_set_state(reservation.id, "CANCELED")


# BR02 – Payments with a status other than approved must not confirm reservations
def test_confirm_payment_with_unapproved_status_does_not_change_state(service):
    # BR02
    flight_id = "FL-BR02-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=3)
    # Attempt to confirm with paymentApproved=False -> reservation must remain CREATED
    service.confirmPayment(reservation.id, paymentApproved=False)
    assert reservation.state == "CREATED"


# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
def test_confirm_with_single_approved_payment_transitions_to_confirmed(service):
    # BR01
    flight_id = "FL-BR01-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=4)
    # Approve payment via confirmPayment -> should atomically confirm reservation
    service.confirmPayment(reservation.id, paymentApproved=True)
    assert reservation.state == "CONFIRMED"


# BR19 – Additional payment attempts for the same reservation must be rejected
def test_second_payment_attempt_for_same_reservation_is_rejected(service):
    # BR19
    flight_id = "FL-BR19-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=5)
    service.confirmPayment(reservation.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=True)


# BR18 – Each reservation may have exactly one associated payment
def test_reservation_has_exactly_one_associated_payment_after_confirmation(service):
    # BR18
    flight_id = "FL-BR18-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=6)
    service.confirmPayment(reservation.id, paymentApproved=True)
    payments = service.get_payments_for_reservation(reservation.id)
    assert len(payments) == 1
    assert payments[0].status == "APPROVED"


# BR03 – Reservation confirmation and payment approval must occur atomically
def test_failed_payment_does_not_leave_reservation_partially_confirmed(service):
    # BR03
    flight_id = "FL-BR03-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=5)
    reservation = service.createReservation(flight_id, seat=7)
    # Simulate underlying storage failure during payment processing via flag
    service.simulate_failure_on_payment_processing = True
    with pytest.raises(Exception):
        service.confirmPayment(reservation.id, paymentApproved=True)
    # After failure, reservation must remain CREATED (no partial commit)
    assert reservation.state == "CREATED"
    payments = service.get_payments_for_reservation(reservation.id)
    assert payments == []


# BR04 – A seat may belong to at most one active reservation per flight
def test_seat_cannot_be_allocated_to_two_active_reservations(service):
    # BR04
    flight_id = "FL-BR04-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res1 = service.createReservation(flight_id, seat=1)
    # reserve second seat different allowed
    res2 = service.createReservation(flight_id, seat=2)
    # Attempt to create another active reservation for seat 1 must be rejected
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)


# BR05 – Canceled reservations must immediately release the associated seat
def test_cancel_releases_seat_immediately(service):
    # BR05
    flight_id = "FL-BR05-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    assert service.is_seat_reserved(flight_id, 1) is True
    service.cancelReservation(res.id)
    assert service.is_seat_reserved(flight_id, 1) is False


# BR06 – Overbooking is not permitted under any circumstances
def test_system_rejects_reservations_that_would_cause_overbooking(service):
    # BR06
    flight_id = "FL-BR06-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=1)
    res = service.createReservation(flight_id, seat=1)
    # Any additional reservation for the same flight must be rejected since only 1 seat exists
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)


# BR07 – Number of confirmed reservations must never exceed total seats
def test_confirming_reservations_never_exceeds_total_seats(service):
    # BR07
    flight_id = "FL-BR07-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=1)
    res1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res1.id, paymentApproved=True)
    # Create another reservation for a different seat number (which doesn't exist) should be rejected
    with pytest.raises(Exception):
        res2 = service.createReservation(flight_id, seat=2)  # seat 2 not existent
    # Attempt to confirm a second reservation when only one seat exists must be rejected
    # To exercise confirming stage, create a pending reservation by using the only seat after cancel
    # (already occupied) -> confirm should never be possible to exceed seats
    # No state change must be allowed that results in confirmed_count > total_seats
    with pytest.raises(Exception):
        # Simulate another reservation creation and confirmation attempt that would exceed capacity
        temp_res = service.createReservation(flight_id, seat=1)
        service.confirmPayment(temp_res.id, paymentApproved=True)


# BR09 – Intermediate or additional states are not permitted
def test_system_does_not_return_intermediate_states(service):
    # BR09
    flight_id = "FL-BR09-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res = service.createReservation(flight_id, seat=1)
    # The API must only expose CREATED, CONFIRMED, or CANCELED; ensure no other value appears
    assert res.state in {"CREATED", "CONFIRMED", "CANCELED"}


# BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
def test_canceled_reservation_rejects_further_payments_or_modifications(service):
    # BR12
    flight_id = "FL-BR12-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)  # cannot modify seat via new reservation referencing same resource id
    with pytest.raises(Exception):
        service._force_set_state(res.id, "CONFIRMED")  # cannot reactivate


# BR13 – Cancellation refund policy based on remaining time: >=24h -> full refund
def test_cancel_at_or_above_24_hours_before_flight_grants_full_refund(service):
    # BR13
    flight_id = "FL-BR13-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res = service.createReservation(flight_id, seat=1)
    # Confirm payment first
    service.confirmPayment(res.id, paymentApproved=True)
    # Cancel when remaining time >=24 hours -> expect refund record of type 'FULL'
    refund = service.cancelReservation(res.id)
    assert refund == "FULL"


# BR13 – Cancellation refund policy based on remaining time: <24h -> no refund
def test_cancel_less_than_24_hours_before_flight_results_in_no_refund(service):
    # BR13
    flight_id = "FL-BR13-002"
    service.add_flight(flight_id, DT_23_HOURS, total_seats=3)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id)
    assert refund == "NONE"


# BR14 – Remaining time until flight must be calculated in exact hours, no rounding
def test_remaining_time_calculated_in_exact_hours_no_rounding(service):
    # BR14
    # Set flight exactly 24 hours from a known internal reference; system must use internal stored flight datetime (BR15)
    flight_id = "FL-BR14-001"
    # Flight at 2026-01-13 10:00:00 is exactly 24 hours from DT_NOW
    DT_EXACT_24 = datetime.datetime(2026, 1, 13, 10, 0, 0)
    service.add_flight(flight_id, DT_EXACT_24, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    # Confirm payment then cancel; policy uses exact hours so 24 hours is considered >=24 -> full refund
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id)
    assert refund == "FULL"


# BR15 – System must use exclusively internally stored flight date/time as temporal reference
def test_system_ignores_external_time_inputs_and_uses_internal_flight_datetime(service):
    # BR15
    flight_id = "FL-BR15-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    # Attempt to pass external 'current_time' parameter must have no effect; system uses internal flight datetime only
    # Simulate passing external time if API allowed (it should not). If API ignores external parameter, cancel behavior based on internal time.
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id, external_now=DT_PAST)  # system must ignore this and base on internally stored flight date
    assert refund == "FULL"


# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
def test_modifying_flight_data_after_confirmation_is_rejected(service):
    # BR16
    flight_id = "FL-BR16-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.modify_flight_datetime(flight_id, DT_23_HOURS)


# BR17 – Indirect modifications of flight data (reference swapping, cloning) are prohibited
def test_indirect_modification_of_flight_object_is_rejected(service):
    # BR17
    flight_id = "FL-BR17-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    # Attempt to replace flight object must be rejected
    with pytest.raises(Exception):
        service.replace_flight_reference(flight_id, {"dateTime": DT_23_HOURS, "totalSeats": 2})


# BR20 – Payments must not be accepted for canceled reservations or after the flight date
def test_payment_rejected_for_canceled_or_past_flight_reservations(service):
    # BR20
    flight_id = "FL-BR20-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    # For a flight in the past:
    past_flight = "FL-BR20-002"
    service.add_flight(past_flight, DT_PAST, total_seats=2)
    res_past = service.createReservation(past_flight, seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(res_past.id, paymentApproved=True)


# BR21 – System operations must be deterministic
def test_same_sequence_of_operations_produces_same_results(service):
    # BR21
    flight_id = "FL-BR21-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    # First run
    res_a = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res_a.id, paymentApproved=True)
    service.cancelReservation(res_a.id)
    result1 = service.get_audit_log_for_reservation(res_a.id)
    # Reset service and repeat exact same sequence
    svc2 = ReservationService()
    svc2.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res_b = svc2.createReservation(flight_id, seat=1)
    svc2.confirmPayment(res_b.id, paymentApproved=True)
    svc2.cancelReservation(res_b.id)
    result2 = svc2.get_audit_log_for_reservation(res_b.id)
    assert result1 == result2


# BR22 – The system must not assume unspecified implicit behaviors
def test_system_does_not_apply_any_implicit_rebooking_or_future_credit_on_cancellation(service):
    # BR22
    flight_id = "FL-BR22-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id)
    # System must not create implicit rebookings or additional credits beyond exact refund policy
    assert service.get_future_credit_for_reservation(res.id) == 0
    assert refund in {"FULL", "NONE"}


# BR23 – Any business rule violation must result in immediate failure with no state change or partial records
def test_business_rule_violation_does_not_modify_state_or_create_records(service):
    # BR23
    flight_id = "FL-BR23-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=1)
    res = service.createReservation(flight_id, seat=1)
    # Trigger violation: attempt second reservation for same seat
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)
    # Ensure original reservation unchanged and no extra records created
    assert res.state == "CREATED"
    assert service.count_records_for_flight(flight_id) == 1  # only the original reservation record exists


# BR24 – Each valid operation must generate exactly one immutable record
def test_each_valid_operation_generates_exactly_one_immutable_record(service):
    # BR24
    flight_id = "FL-BR24-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    # Create reservation -> one record
    res = service.createReservation(flight_id, seat=1)
    assert service.count_records_for_reservation(res.id) == 1
    # Confirm payment -> exactly one additional immutable record (payment+confirmation as atomic record)
    service.confirmPayment(res.id, paymentApproved=True)
    assert service.count_records_for_reservation(res.id) == 2
    # Cancel -> one more record
    service.cancelReservation(res.id)
    assert service.count_records_for_reservation(res.id) == 3


# BR25 – Failed operations must not generate persistent records
def test_failed_operations_do_not_create_persistent_records(service):
    # BR25
    flight_id = "FL-BR25-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=1)
    res = service.createReservation(flight_id, seat=1)
    initial_record_count = service.count_records_for_reservation(res.id)
    # Cause a failure: second payment attempt
    service.confirmPayment(res.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    # Ensure no new record persisted from failed attempt
    assert service.count_records_for_reservation(res.id) == initial_record_count + 1


# BR26 – Operations on one reservation must not affect other reservations, flights, or seats
def test_operations_on_one_reservation_do_not_affect_others(service):
    # BR26
    flight_id = "FL-BR26-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=3)
    res1 = service.createReservation(flight_id, seat=1)
    res2 = service.createReservation(flight_id, seat=2)
    service.confirmPayment(res1.id, paymentApproved=True)
    # Cancel res1 and ensure res2 remains unchanged
    service.cancelReservation(res1.id)
    assert res2.state == "CREATED"
    assert service.is_seat_reserved(flight_id, 2) is False  # not reserved until confirmed
    # Confirming res2 should still be allowed independently
    service.confirmPayment(res2.id, paymentApproved=True)
    assert res2.state == "CONFIRMED"


# FR02 – Confirm payment and, atomically, confirm the reservation
def test_confirm_payment_atomically_confirms_reservation(service):
    # FR02
    flight_id = "FL-FR02-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"


# FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
def test_seat_availability_strictly_controlled_on_confirmation(service):
    # FR03
    flight_id = "FL-FR03-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res1 = service.createReservation(flight_id, seat=1)
    res2 = service.createReservation(flight_id, seat=2)
    service.confirmPayment(res1.id, paymentApproved=True)
    # While res1 is confirmed, attempting to confirm another reservation for the same seat must be rejected
    with pytest.raises(Exception):
        # Attempt to create/confirm another reservation on the same seat should fail
        res_conflict = service.createReservation(flight_id, seat=1)
        service.confirmPayment(res_conflict.id, paymentApproved=True)


# FR04 – Cancel reservations while strictly respecting refund policy based on remaining time
def test_cancel_respects_refund_policy_based_on_remaining_time(service):
    # FR04
    flight_id = "FL-FR04-001"
    service.add_flight(flight_id, DT_23_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id)
    assert refund == "NONE"


# FR05 – Prevent any invalid modification of state, flight data, seat, or payment
def test_invalid_modification_attempts_are_rejected(service):
    # FR05
    flight_id = "FL-FR05-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    with pytest.raises(Exception):
        service.modify_reservation_seat(res.id, 2)
    with pytest.raises(Exception):
        service.modify_reservation_state(res.id, "CANCELED")  # must go through cancelReservation
    with pytest.raises(Exception):
        service.add_payment_to_reservation(res.id, {"status": "APPROVED"})


# FR06 – Do not allow overbooking at any stage of the process
def test_overbooking_prevented_at_creation_and_confirmation_stages(service):
    # FR06
    flight_id = "FL-FR06-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=1)
    res1 = service.createReservation(flight_id, seat=1)
    service.confirmPayment(res1.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.createReservation(flight_id, seat=1)
    # Even attempts to confirm a pending reservation that would cause overbooking must be rejected
    with pytest.raises(Exception):
        pending = service.createReservation(flight_id, seat=1)
        service.confirmPayment(pending.id, paymentApproved=True)


# FR07 – Do not allow multiple, partial, or late payments
def test_multiple_partial_or_late_payments_are_rejected(service):
    # FR07
    flight_id = "FL-FR07-001"
    service.add_flight(flight_id, DT_PAST, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    # Late payment (flight in past) must be rejected
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=True)
    # Multiple payments for same reservation must be rejected (after a successful one)
    flight_id2 = "FL-FR07-002"
    service.add_flight(flight_id2, DT_25_HOURS, total_seats=2)
    res2 = service.createReservation(flight_id2, seat=1)
    service.confirmPayment(res2.id, paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(res2.id, paymentApproved=True)


# FR08 – Do not return intermediate states, explanatory messages, or partial results
def test_api_returns_only_final_states_and_no_intermediate_messages(service):
    # FR08
    flight_id = "FL-FR08-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    # confirmPayment must result in final state without intermediate states in observable API
    service.confirmPayment(res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"


# FR09 – Ensure failures do not modify state or produce persistent side effects
def test_failure_during_operation_does_not_modify_state_or_persist_side_effects(service):
    # FR09
    flight_id = "FL-FR09-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    service.simulate_failure_on_cancel = True
    with pytest.raises(Exception):
        service.cancelReservation(res.id)
    # After failed cancel, reservation must remain CONFIRMED if it was confirmed
    # First confirm, then attempt failing cancel
    service.simulate_failure_on_cancel = False
    service.confirmPayment(res.id, paymentApproved=True)
    service.simulate_failure_on_cancel = True
    with pytest.raises(Exception):
        service.cancelReservation(res.id)
    assert res.state == "CONFIRMED"


# FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment
def test_system_uses_only_internally_stored_data_without_external_enrichment(service):
    # FR10
    flight_id = "FL-FR10-001"
    service.add_flight(flight_id, DT_25_HOURS, total_seats=2)
    res = service.createReservation(flight_id, seat=1)
    # Attempt to influence behavior via external side-channel must have no effect
    service.external_influence = {"force_refund": "FULL"}
    service.confirmPayment(res.id, paymentApproved=True)
    refund = service.cancelReservation(res.id)
    # Refund decision must rely solely on internal flight datetime and not on external_influence
    assert refund in {"FULL", "NONE"}
```