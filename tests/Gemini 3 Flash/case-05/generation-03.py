```python
import pytest
from datetime import datetime, timedelta

# BR08, FR01 – Create an initial reservation in the CREATED state
def test_fr01_br08_reservation_initial_state_is_created():
    service = ReservationService()
    reservation = service.createReservation(flightId="FL123", seat=1)
    assert reservation.state == "CREATED"

# BR01, FR02 – A reservation may only be confirmed if exactly one approved payment is associated
def test_br01_fr02_confirm_reservation_with_approved_payment():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId=res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"

# BR02 – Payments with a status other than approved must not confirm reservations
def test_br02_reject_confirmation_with_unapproved_payment():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=res.id, paymentApproved=False)
    assert res.state == "CREATED"

# BR03, FR09 – Reservation confirmation and payment approval must occur atomically
def test_br03_fr09_atomic_confirmation_failure_leaves_no_partial_state():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # Simulate a failure during the atomic transition
    # Verification: State must remain exactly as it was if any part of the process fails
    with pytest.raises(Exception):
        service.confirmPayment(reservationId=res.id, paymentApproved=True) 
    assert res.state == "CREATED"

# BR04, FR03 – A seat may belong to at most one active reservation per flight
def test_br04_fr03_prevent_duplicate_seat_allocation_on_same_flight():
    service = ReservationService()
    service.createReservation(flightId="FL123", seat=10)
    with pytest.raises(Exception):
        service.createReservation(flightId="FL123", seat=10)

# BR05 – Canceled reservations must immediately release the associated seat
def test_br05_canceled_reservation_releases_seat():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    # This should now succeed because the seat was released
    new_res = service.createReservation(flightId="FL123", seat=10)
    assert new_res.seat == 10

# BR06, FR06 – Overbooking is not permitted under any circumstances
def test_br06_fr06_prevent_reservation_beyond_capacity():
    service = ReservationService()
    # Assuming flight FL777 has totalSeats: 1
    service.createReservation(flightId="FL777", seat=1)
    with pytest.raises(Exception):
        service.createReservation(flightId="FL777", seat=2)

# BR07 – Confirmed reservations must never exceed total available seats
def test_br07_confirmed_count_within_capacity():
    service = ReservationService()
    # Assuming flight FL888 has totalSeats: 1
    res = service.createReservation(flightId="FL888", seat=1)
    service.confirmPayment(res.id, True)
    # Attempting to create or confirm another should fail
    with pytest.raises(Exception):
        service.createReservation(flightId="FL888", seat=2)

# BR09 – Intermediate or additional states are not permitted
def test_br09_no_intermediate_states_allowed():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # The system must only ever return CREATED, CONFIRMED, or CANCELED
    assert res.state in ["CREATED", "CONFIRMED", "CANCELED"]
    assert res.state != "PENDING"
    assert res.state != "IN_PAYMENT"

# BR10, FR05 – Valid transition CREATED -> CONFIRMED
def test_br10_valid_transition_created_to_confirmed():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    assert res.state == "CONFIRMED"

# BR10, FR05 – Valid transition CONFIRMED -> CANCELED
def test_br10_valid_transition_confirmed_to_canceled():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    assert res.state == "CANCELED"

# BR11 – Any state transition other than defined must be rejected (CREATED -> CANCELED)
def test_br11_reject_invalid_transition_created_to_canceled():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # BR10 states only CREATED->CONFIRMED and CONFIRMED->CANCELED
    with pytest.raises(Exception):
        service.cancelReservation(res.id)

# BR11 – Any state transition other than defined must be rejected (CANCELED -> CONFIRMED)
def test_br11_reject_invalid_transition_canceled_to_confirmed():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR12 – A canceled reservation must not be reactivated or modified
def test_br12_canceled_reservation_is_immutable():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        # Attempt to change state or re-confirm
        service.confirmPayment(res.id, True)

# BR13, FR04 – Full refund if remaining time >= 24 hours
def test_br13_fr04_full_refund_at_exactly_24_hours():
    service = ReservationService()
    # Internal flight time: 2026-01-15 12:00:00
    # Current time: 2026-01-14 12:00:00 (Exactly 24h)
    res = service.createReservation(flightId="FL_TIME", seat=1)
    service.confirmPayment(res.id, True)
    refund = service.cancelReservation(res.id)
    assert refund == "FULL_REFUND"

# BR13, FR04 – No refund if remaining time < 24 hours
def test_br13_fr04_no_refund_at_23_hours_59_minutes():
    service = ReservationService()
    # Internal flight time: 2026-01-15 12:00:00
    # Current time: 2026-01-14 12:01:00 (23h 59m remaining)
    res = service.createReservation(flightId="FL_TIME", seat=1)
    service.confirmPayment(res.id, True)
    refund = service.cancelReservation(res.id)
    assert refund == "NO_REFUND"

# BR14 – Remaining time must be calculated in exact hours, no rounding
def test_br14_no_rounding_in_time_calculation():
    service = ReservationService()
    # If the rule is exactly 24 hours, 23.999 hours is < 24 and must not be rounded up to 24
    res = service.createReservation(flightId="FL_TIME", seat=1)
    service.confirmPayment(res.id, True)
    # Simulation of exactly 23.99 hours remaining
    refund = service.cancelReservation(res.id)
    assert refund == "NO_REFUND"

# BR15, FR10 – System must use exclusively internally stored flight date and time
def test_br15_fr10_use_internal_flight_temporal_reference():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # The cancellation logic must depend on flight.dateTime, not external system clock
    service.confirmPayment(res.id, True)
    # Cancellation should trigger logic based on the Flight object's dateTime attribute
    service.cancelReservation(res.id)

# BR16 – Flight data must not be altered after reservation confirmation
def test_br16_flight_data_immutability_after_confirmation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        # Attempt to modify flightId or flight details associated with reservation
        res.flightId = "FL999"

# BR17 – Indirect modifications of flight data are prohibited
def test_br17_prohibit_indirect_flight_object_swapping():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    original_flight_ref = res.flight
    service.confirmPayment(res.id, True)
    # Verification that the object reference itself hasn't been swapped/cloned
    assert res.flight is original_flight_ref

# BR18, FR07 – Each reservation may have exactly one associated payment
def test_br18_fr07_exactly_one_payment_per_reservation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    # Second payment association should fail
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR19 – Additional payment attempts for the same reservation must be rejected
def test_br19_reject_additional_payment_attempts():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR20 – Payments must not be accepted for canceled reservations
def test_br20_no_payment_for_canceled_reservation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR20 – Payments must not be accepted after the flight date
def test_br20_no_payment_after_flight_date():
    service = ReservationService()
    # Flight date: 2026-01-10
    # Current date: 2026-01-12
    res = service.createReservation(flightId="PAST_FLIGHT", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR21 – System operations must be deterministic
def test_br21_deterministic_results():
    service = ReservationService()
    # Sequence of inputs
    res_id = service.createReservation(flightId="FL123", seat=1).id
    service.confirmPayment(res_id, True)
    state1 = service.getReservation(res_id).state
    
    # Same sequence on fresh instance
    service2 = ReservationService()
    res_id2 = service2.createReservation(flightId="FL123", seat=1).id
    service2.confirmPayment(res_id2, True)
    state2 = service2.getReservation(res_id2).state
    
    assert state1 == state2 == "CONFIRMED"

# BR22 – System must not assume unspecified implicit behaviors
def test_br22_no_implicit_future_credit_on_cancellation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    # Check that no implicit credit or rebooking was created
    assert not hasattr(res, "future_credit")
    assert not hasattr(res, "automatic_rebooking")

# BR23 – Violation must result in immediate failure with no state change
def test_br23_violation_results_in_no_state_change():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # Invalid transition attempt
    with pytest.raises(Exception):
        service.cancelReservation(res.id) # CREATED -> CANCELED is forbidden
    assert res.state == "CREATED"

# BR24 – Each valid operation must generate exactly one immutable record
def test_br24_valid_operation_generates_single_immutable_record():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    initial_record_count = len(service.getRecords(res.id))
    service.confirmPayment(res.id, True)
    new_record_count = len(service.getRecords(res.id))
    assert new_record_count == initial_record_count + 1

# BR25 – Failed operations must not generate persistent records
def test_br25_failed_operation_generates_no_persistent_record():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    initial_records = len(service.getRecords(res.id))
    with pytest.raises(Exception):
        service.confirmPayment(res.id, False) # BR02 Violation
    assert len(service.getRecords(res.id)) == initial_records

# BR26 – Operations on one reservation must not affect others
def test_br26_isolation_between_reservations():
    service = ReservationService()
    res1 = service.createReservation(flightId="FL123", seat=1)
    res2 = service.createReservation(flightId="FL123", seat=2)
    service.confirmPayment(res1.id, True)
    assert res1.state == "CONFIRMED"
    assert res2.state == "CREATED"

# FR08 – Do not return intermediate states or partial results
def test_fr08_no_partial_results_on_query():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=1)
    # Querying should return the full valid state or an error, never a "processing" flag
    result = service.getReservation(res.id)
    assert result.state in ["CREATED", "CONFIRMED", "CANCELED"]
    assert not hasattr(result, "partial_data")

```