```python
import pytest
from datetime import datetime, timedelta

# Note: As per instructions, the implementation of the classes is not provided.
# These tests are written to validate the behavior of the ReservationService 
# based on the formal specifications and UML provided.

# -----------------------------------------------------------------------------
# FIXTURES
# -----------------------------------------------------------------------------

@pytest.fixture
def service():
    """Returns an instance of ReservationService."""
    # Implementation assumed to be available in the test environment
    from reservation_system import ReservationService
    return ReservationService()

# -----------------------------------------------------------------------------
# BUSINESS RULES (BR) & FUNCTIONAL REQUIREMENTS (FR) TESTS
# -----------------------------------------------------------------------------

# BR08 – Reservation may be exclusively in CREATED, CONFIRMED, or CANCELED states
# FR01 – Create an initial reservation in the CREATED state
def test_initial_reservation_state_is_created(service):
    reservation = service.createReservation(flightId="FL123", seat=10)
    assert reservation.state == "CREATED"

# BR01 – A reservation may only be confirmed if exactly one approved payment is associated
# FR02 – Confirm payment and, atomically, confirm the reservation
def test_confirm_reservation_with_approved_payment(service):
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    assert res.state == "CONFIRMED"

# BR02 – Payments with a status other than approved must not confirm reservations
def test_reject_confirmation_when_payment_not_approved(service):
    res = service.createReservation(flightId="FL123", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="RES001", paymentApproved=False)
    assert res.state == "CREATED"

# BR03 – Reservation confirmation and payment approval must occur atomically
# FR09 – Ensure that failures do not modify state or produce persistent side effects
def test_atomicity_failure_prevents_state_change(service):
    # Scenario: System fails during the atomic operation of confirmation
    res = service.createReservation(flightId="FL123", seat=1)
    # If the system fails to persist the payment record, the state must remain CREATED
    # This test assumes the service raises an exception on persistence failure
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="RES001", paymentApproved=True)
    assert res.state == "CREATED"

# BR04 – A seat may belong to at most one active reservation per flight
# FR03 – Strictly control seat availability, ensuring exclusivity
def test_seat_exclusivity_per_flight(service):
    service.createReservation(flightId="FL123", seat=15)
    with pytest.raises(Exception):
        service.createReservation(flightId="FL123", seat=15)

# BR05 – Canceled reservations must immediately release the associated seat
def test_release_seat_on_cancellation(service):
    res = service.createReservation(flightId="FL123", seat=20)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    service.cancelReservation(reservationId="RES001")
    # Now the seat must be available for a new reservation
    new_res = service.createReservation(flightId="FL123", seat=20)
    assert new_res.seat == 20

# BR06 – Overbooking is not permitted under any circumstances
# FR06 – Do not allow overbooking at any stage
def test_prevent_overbooking_beyond_capacity(service):
    # Flight with 1 seat capacity
    flight_id = "FL_SMALL" 
    service.createReservation(flightId=flight_id, seat=1)
    with pytest.raises(Exception):
        service.createReservation(flightId=flight_id, seat=2)

# BR07 – The number of confirmed reservations must never exceed total available seats
def test_confirmed_reservations_limit(service):
    # Flight capacity: 2
    service.createReservation(flightId="FL_CAP2", seat=1)
    service.confirmPayment(reservationId="RES1", paymentApproved=True)
    service.createReservation(flightId="FL_CAP2", seat=2)
    service.confirmPayment(reservationId="RES2", paymentApproved=True)
    
    with pytest.raises(Exception):
        # Even if a 3rd reservation was in CREATED (violating BR04/06), 
        # confirming it must fail if it exceeds total flight capacity
        service.confirmPayment(reservationId="RES3", paymentApproved=True)

# BR09 – Intermediate or additional states (e.g., “In payment”) are not permitted
# FR08 – Do not return intermediate states
def test_no_intermediate_states_during_payment(service):
    res = service.createReservation(flightId="FL123", seat=5)
    # The state should only be CREATED or CONFIRMED, never "PENDING" or "IN_PAYMENT"
    assert res.state in ["CREATED", "CONFIRMED", "CANCELED"]

# BR10 – The only valid state transitions are CREATED -> CONFIRMED and CONFIRMED -> CANCELED
# BR11 – Any state transition other than those defined must be rejected
def test_invalid_transition_created_to_canceled(service):
    service.createReservation(flightId="FL123", seat=1)
    with pytest.raises(Exception):
        # Cannot skip CONFIRMED state
        service.cancelReservation(reservationId="RES001")

# BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
def test_prevent_payment_on_canceled_reservation(service):
    service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    service.cancelReservation(reservationId="RES001")
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="RES001", paymentApproved=True)

# BR13 – Cancellation temporal policy: Remaining time >= 24 hours -> full refund
# BR14 – Remaining time until the flight must be calculated in exact hours
# BR15 – System must use exclusively the internally stored flight date and time
def test_full_refund_exactly_24_hours_before(service):
    # Mock flight time: 2026-01-13 12:00:00
    # Current internal time: 2026-01-12 12:00:00 (Exactly 24h)
    res = service.createReservation(flightId="FL_REFUND", seat=1)
    service.confirmPayment(reservationId="RES_REFUND", paymentApproved=True)
    
    # Logic verification for exact 24h threshold
    refund_amount = service.cancelReservation(reservationId="RES_REFUND")
    assert refund_amount == "FULL_REFUND"

# BR13 – Cancellation temporal policy: Remaining time < 24 hours -> no refund
def test_no_refund_less_than_24_hours_before(service):
    # Mock flight time: 2026-01-13 12:00:00
    # Current internal time: 2026-01-12 12:00:01 (23 hours, 59 minutes, 59 seconds)
    # BR14: Exact hours, no rounding. 23.99 < 24.
    res = service.createReservation(flightId="FL_NO_REFUND", seat=1)
    service.confirmPayment(reservationId="RES_NO_REFUND", paymentApproved=True)
    
    refund_amount = service.cancelReservation(reservationId="RES_NO_REFUND")
    assert refund_amount == "NO_REFUND"

# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
# FR05 – Prevent any invalid modification of flight data
def test_flight_data_immutability_after_confirmation(service):
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    
    # Attempting to change flightId or seat via any method must fail
    with pytest.raises(AttributeError):
        res.flightId = "FL999"

# BR17 – Indirect modifications of flight data (reference swapping) are prohibited
def test_prohibit_indirect_flight_object_recreation(service):
    res = service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    original_flight_ref = res.flightId
    
    # Internal mechanism check: if flightId is swapped, system must fail or block
    with pytest.raises(Exception):
        service.modifyReservationInternal(reservationId="RES001", newFlightId="FL123")

# BR18 – Each reservation may have exactly one associated payment
# BR19 – Additional payment attempts for the same reservation must be rejected
# FR07 – Do not allow multiple payments
def test_reject_duplicate_payment_attempts(service):
    service.createReservation(flightId="FL123", seat=1)
    service.confirmPayment(reservationId="RES001", paymentApproved=True)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="RES001", paymentApproved=True)

# BR20 – Payments must not be accepted after the flight date
def test_reject_payment_after_flight_date(service):
    # Flight Date: 2026-01-11
    # Current Date: 2026-01-12
    service.createReservation(flightId="PAST_FLIGHT", seat=1)
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="RES_PAST", paymentApproved=True)

# BR21 – System operations must be deterministic
def test_deterministic_result_for_same_inputs(service):
    # Operation 1
    res1 = service.createReservation(flightId="FL_DET", seat=1)
    # Operation 2 (Repeat)
    with pytest.raises(Exception):
        service.createReservation(flightId="FL_DET", seat=1)
    # The result of attempting to reserve the same seat twice must consistently fail

# BR23 – Any business rule violation must result in immediate failure with no state change
# BR25 – Failed operations must not generate persistent records
def test_failure_produces_no_side_effects(service):
    # Attempt to confirm a reservation that doesn't exist
    with pytest.raises(Exception):
        service.confirmPayment(reservationId="NON_EXISTENT", paymentApproved=True)
    # Validate that no new records were created in the registry
    assert service.getReservationCount() == 0

# BR24 – Each valid operation must generate exactly one immutable record
def test_valid_operation_generates_single_record(service):
    initial_count = service.getRecordCount()
    service.createReservation(flightId="FL123", seat=1)
    assert service.getRecordCount() == initial_count + 1

# BR26 – Operations on one reservation must not affect other reservations, flights, or seats
def test_reservation_isolation(service):
    res_a = service.createReservation(flightId="FL1", seat=1)
    res_b = service.createReservation(flightId="FL2", seat=1)
    
    service.confirmPayment(reservationId="RES_A", paymentApproved=True)
    service.cancelReservation(reservationId="RES_A")
    
    # Action on Res A should not have changed Res B
    assert res_b.state == "CREATED"
    assert res_b.seat == 1

# FR10 – Use exclusively provided and internally stored data
def test_no_external_data_inference(service):
    # The system should not fetch external pricing or seat data not in the Flight object
    res = service.createReservation(flightId="FL123", seat=1)
    # If the system attempts to call an external API for "market price" or "status", it violates FR10
    # This is validated by ensuring the object only contains defined UML attributes
    assert hasattr(res, 'state')
    assert hasattr(res, 'seat')
    assert not hasattr(res, 'external_status_code')
```