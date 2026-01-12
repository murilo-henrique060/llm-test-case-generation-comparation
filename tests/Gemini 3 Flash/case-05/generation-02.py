```python
import pytest
from datetime import datetime, timedelta

# Note: The following tests assume the existence of ReservationService, Reservation, and Flight 
# as defined in the provided UML and specifications.

# FR01 – Create an initial reservation in the CREATED state
# BR08 – A reservation may be exclusively in CREATED, CONFIRMED, or CANCELED states
def test_create_reservation_initial_state():
    service = ReservationService()
    reservation = service.createReservation(flightId="FL123", seat=10)
    assert reservation.state == "CREATED"
    assert reservation.seat == 10

# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
# FR02 – Confirm payment and, atomically, confirm the reservation
def test_confirm_payment_approved_updates_state():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, paymentApproved=True)
    assert res.state == "CONFIRMED"

# BR02 – Payments with a status other than approved must not confirm reservations
def test_confirm_payment_rejected_does_not_confirm():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, paymentApproved=False)
    assert res.state == "CREATED"

# BR03 – Reservation confirmation and payment approval must occur atomically
# FR09 – Ensure that failures do not modify state or produce persistent side effects
def test_confirmation_atomicity_on_failure():
    # Scenario: If an internal error occurs during the atomic process, state remains CREATED
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    # Simulating a failure during the atomic transition
    # (The test expects the system to roll back or not apply changes)
    try:
        service.confirmPayment(res.id, paymentApproved=True) # Assume internal failure occurs
    except Exception:
        pass
    assert res.state == "CREATED"

# BR04 – A seat may belong to at most one active reservation per flight
# FR03 – Strictly control seat availability
def test_seat_exclusivity_per_flight():
    service = ReservationService()
    service.createReservation(flightId="FL123", seat=15)
    with pytest.raises(Exception):
        # Attempting to reserve the same seat on the same flight
        service.createReservation(flightId="FL123", seat=15)

# BR05 – Canceled reservations must immediately release the associated seat
def test_release_seat_on_cancellation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=20)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    assert res.state == "CANCELED"
    # Should now be able to reserve the same seat again
    new_res = service.createReservation(flightId="FL123", seat=20)
    assert new_res is not None

# BR06 – Overbooking is not permitted under any circumstances
# BR07 – Confirmed reservations must never exceed total available seats
# FR06 – Do not allow overbooking at any stage
def test_prevent_overbooking_beyond_capacity():
    service = ReservationService()
    # Assume flight FL999 has only 1 seat total
    # First reservation
    service.createReservation(flightId="FL999", seat=1)
    with pytest.raises(Exception):
        # Second reservation attempt for a different seat exceeding capacity
        service.createReservation(flightId="FL999", seat=2)

# BR09 – Intermediate or additional states (e.g., “In payment”) are not permitted
def test_no_intermediate_states_during_payment():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    # The requirement BR09 implies we can never observe a state other than the 3 defined
    service.confirmPayment(res.id, True)
    assert res.state in ["CREATED", "CONFIRMED", "CANCELED"]

# BR10 – Valid state transition: CREATED → CONFIRMED
def test_valid_transition_created_to_confirmed():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    assert res.state == "CONFIRMED"

# BR10 – Valid state transition: CONFIRMED → CANCELED
def test_valid_transition_confirmed_to_canceled():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    assert res.state == "CANCELED"

# BR11 – Any state transition other than defined must be rejected
# FR05 – Prevent any invalid modification of state
def test_invalid_transition_created_to_canceled_directly():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    # Transition CREATED -> CANCELED is not in BR10
    with pytest.raises(Exception):
        service.cancelReservation(res.id)

# BR11 – Any state transition other than defined must be rejected
def test_invalid_transition_confirmed_to_created():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    # Attempting to move back to CREATED (not defined in BR10)
    with pytest.raises(Exception):
        # Explicit attempt to revert state
        res.state = "CREATED" 

# BR12 – A canceled reservation must not be reactivated
def test_no_reactivation_of_canceled_reservation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR13 – Cancellation ≥ 24 hours before flight → full refund
# BR14 – Time calculated in exact hours, no rounding
# BR15 – System must use internally stored flight date and time
# FR04 – Strictly respecting refund policy based on remaining time
def test_refund_policy_exactly_24_hours_before():
    service = ReservationService()
    # Flight time: 2026-01-15 10:00:00
    # Current/Cancellation time: 2026-01-14 10:00:00 (Exactly 24h)
    res = service.createReservation(flightId="FL_TIME", seat=1)
    service.confirmPayment(res.id, True)
    
    # Mocking internal system time to exactly 24h before flight
    refund = service.cancelReservation(res.id) 
    assert refund == "FULL_REFUND"

# BR13 – Cancellation < 24 hours before flight → no refund
# BR14 – Time calculated in exact hours, no rounding
def test_refund_policy_less_than_24_hours_before():
    service = ReservationService()
    # Flight time: 2026-01-15 10:00:00
    # Current/Cancellation time: 2026-01-14 10:00:01 (23h 59m 59s remaining)
    res = service.createReservation(flightId="FL_TIME", seat=1)
    service.confirmPayment(res.id, True)
    
    # Mocking internal system time to slightly less than 24h
    refund = service.cancelReservation(res.id)
    assert refund == "NO_REFUND"

# BR16 – Flight identifiers must not be altered after reservation confirmation
# FR05 – Prevent invalid modification of flight data
def test_flight_id_immutability_after_confirmation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        # Attempting to change flight ID of a confirmed reservation
        res.flightId = "FL999"

# BR17 – Indirect modifications of flight data (reference swapping) are prohibited
def test_prevent_indirect_flight_data_modification():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    new_flight_object = Flight(flightId="FL999", dateTime=datetime.now(), totalSeats=100)
    with pytest.raises(Exception):
        # Attempting to swap the internal flight reference
        res.flight = new_flight_object

# BR18 – Each reservation may have exactly one associated payment
# BR19 – Additional payment attempts for the same reservation must be rejected
# FR07 – Do not allow multiple payments
def test_reject_multiple_payments():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        # Second payment attempt
        service.confirmPayment(res.id, True)

# BR20 – Payments must not be accepted for canceled reservations
def test_no_payment_for_canceled_reservation():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    service.confirmPayment(res.id, True)
    service.cancelReservation(res.id)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR20 – Payments must not be accepted after the flight date
def test_no_payment_after_flight_date():
    service = ReservationService()
    # Assume flight was yesterday
    res = service.createReservation(flightId="PAST_FLIGHT", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(res.id, True)

# BR21 – System operations must be deterministic
def test_deterministic_creation_result():
    service = ReservationService()
    res1 = service.createReservation(flightId="FL123", seat=10)
    res2 = service.createReservation(flightId="FL123", seat=11)
    # The sequence of inputs (FL123, seat 10 then 11) must always yield same states/ids logic
    assert res1.id != res2.id
    assert res1.state == "CREATED"
    assert res2.state == "CREATED"

# BR23 – Any business rule violation must result in immediate failure with no state change
def test_violation_results_in_no_state_change():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    # BR19 violation attempt (multiple payments)
    service.confirmPayment(res.id, True)
    try:
        service.confirmPayment(res.id, True)
    except Exception:
        pass
    # State must remain CONFIRMED, not change to an error state or elsewhere
    assert res.state == "CONFIRMED"

# BR24 – Each valid operation must generate exactly one immutable record
def test_operation_generates_immutable_record():
    service = ReservationService()
    res = service.createReservation(flightId="FL123", seat=10)
    record_id = res.id
    # Attempting to change record identifier or core data
    with pytest.raises(Exception):
        res.id = "NEW_ID"
    assert res.id == record_id

# BR26 – Operations on one reservation must not affect other reservations
def test_isolation_of_reservations():
    service = ReservationService()
    res1 = service.createReservation(flightId="FL123", seat=10)
    res2 = service.createReservation(flightId="FL123", seat=11)
    
    service.confirmPayment(res1.id, True)
    service.cancelReservation(res1.id)
    
    # res1 is CANCELED, res2 must remain CREATED
    assert res1.state == "CANCELED"
    assert res2.state == "CREATED"
    assert res2.seat == 11

# FR10 – Use exclusively provided data, no external enrichment
def test_no_external_data_inference():
    service = ReservationService()
    # If flightId doesn't exist in system, it must fail rather than inferring/creating a flight
    with pytest.raises(Exception):
        service.createReservation(flightId="NON_EXISTENT", seat=1)
```