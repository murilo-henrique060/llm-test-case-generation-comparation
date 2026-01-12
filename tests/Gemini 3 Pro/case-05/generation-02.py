```python
import pytest
from datetime import datetime, timedelta

# -------------------------------------------------------------------------
# MOCKS AND STUBS FOR TEST CONTEXT
# -------------------------------------------------------------------------
# Since the implementation is not provided, we assume the existence of these 
# classes and exceptions to make the tests syntactically valid and runnable 
# against a compliant implementation.
# -------------------------------------------------------------------------

class DomainException(Exception):
    """Base exception for business rule violations."""
    pass

class ReservationState:
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"

# Assumed interfaces based on the prompt's Class Diagram
# Use these types for type hinting in tests if needed, 
# but tests strictly rely on behavior.

# -------------------------------------------------------------------------
# TESTS
# -------------------------------------------------------------------------

@pytest.fixture
def service():
    """
    Fixture to initialize the ReservationService.
    Assumes a fresh instance for each test to ensure isolation (BR26).
    """
    from reservation_system import ReservationService
    return ReservationService()

@pytest.fixture
def future_flight_date():
    """Returns a datetime well into the future (e.g., 48 hours)."""
    return datetime.now() + timedelta(hours=48)

@pytest.fixture
def near_flight_date():
    """Returns a datetime less than 24 hours from now (e.g., 20 hours)."""
    return datetime.now() + timedelta(hours=20)

# -------------------------------------------------------------------------
# CREATION AND INITIAL STATE
# -------------------------------------------------------------------------

def test_create_reservation_initial_state(service, future_flight_date):
    """
    BR08 – A reservation may be exclusively in one of the following states: CREATED, CONFIRMED, CANCELED.
    FR01 – Create an initial reservation in the CREATED state.
    """
    flight_id = "FL100"
    seat = 1
    
    # Setup: Create flight with available seats
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    
    reservation = service.create_reservation(flight_id, seat)
    
    assert reservation.state == ReservationState.CREATED
    assert reservation.seat == seat

def test_no_intermediate_states_on_creation(service, future_flight_date):
    """
    BR09 – Intermediate or additional states are not permitted.
    FR08 – Do not return intermediate states.
    """
    flight_id = "FL101"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    
    reservation = service.create_reservation(flight_id, seat=1)
    
    assert reservation.state not in ["PENDING", "IN_PAYMENT", "EXPIRED", "DRAFT"]
    assert reservation.state == ReservationState.CREATED

# -------------------------------------------------------------------------
# SEAT ALLOCATION AND OVERBOOKING
# -------------------------------------------------------------------------

def test_prevent_duplicate_seat_allocation_created_state(service, future_flight_date):
    """
    BR04 – A seat may belong to at most one active reservation per flight.
    FR03 – Strictly control seat availability, ensuring exclusivity per active reservation.
    FR06 – Do not allow overbooking at any stage.
    """
    flight_id = "FL200"
    seat = 10
    service.register_flight(flight_id, future_flight_date, total_seats=50)
    
    # First reservation
    service.create_reservation(flight_id, seat)
    
    # Attempt second reservation for same seat
    with pytest.raises(DomainException):
        service.create_reservation(flight_id, seat)

def test_prevent_overbooking_total_capacity(service, future_flight_date):
    """
    BR06 – Overbooking is not permitted under any circumstances.
    BR07 – The number of confirmed reservations must never exceed available seats.
    FR06 – Do not allow overbooking at any stage of the process.
    """
    flight_id = "FL201"
    total_seats = 1
    service.register_flight(flight_id, future_flight_date, total_seats=total_seats)
    
    # Fill capacity
    service.create_reservation(flight_id, seat=1)
    
    # Attempt to exceed capacity with a new valid seat index
    with pytest.raises(DomainException):
        service.create_reservation(flight_id, seat=2)

# -------------------------------------------------------------------------
# PAYMENT AND CONFIRMATION
# -------------------------------------------------------------------------

def test_confirm_reservation_success(service, future_flight_date):
    """
    BR01 – A reservation may only be confirmed if exactly one approved payment is associated.
    BR03 – Reservation confirmation and payment approval must occur atomically.
    BR10 – Valid transition: CREATED → CONFIRMED.
    FR02 – Confirm payment and, atomically, confirm the reservation.
    """
    flight_id = "FL300"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    reservation = service.create_reservation(flight_id, seat=1)
    
    service.confirm_payment(reservation.id, payment_approved=True)
    
    updated_reservation = service.get_reservation(reservation.id)
    assert updated_reservation.state == ReservationState.CONFIRMED

def test_do_not_confirm_if_payment_rejected(service, future_flight_date):
    """
    BR02 – Payments with a status other than approved must not confirm reservations.
    BR23 – Any business rule violation must result in immediate failure with no state change.
    BR25 – Failed operations must not generate persistent records.
    """
    flight_id = "FL301"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    reservation = service.create_reservation(flight_id, seat=1)
    
    with pytest.raises(DomainException):
        service.confirm_payment(reservation.id, payment_approved=False)
    
    updated_reservation = service.get_reservation(reservation.id)
    assert updated_reservation.state == ReservationState.CREATED

def test_reject_multiple_payments_for_reservation(service, future_flight_date):
    """
    BR18 – Each reservation may have exactly one associated payment.
    BR19 – Additional payment attempts for the same reservation must be rejected.
    FR07 – Do not allow multiple, partial, or late payments.
    """
    flight_id = "FL302"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    reservation = service.create_reservation(flight_id, seat=1)
    
    # First payment success
    service.confirm_payment(reservation.id, payment_approved=True)
    
    # Second payment attempt
    with pytest.raises(DomainException):
        service.confirm_payment(reservation.id, payment_approved=True)

def test_reject_payment_after_flight_date(service):
    """
    BR20 – Payments must not be accepted for canceled reservations or after the flight date.
    FR07 – Do not allow ... late payments.
    """
    # Flight in the past
    past_date = datetime.now() - timedelta(hours=1)
    flight_id = "FL303"
    service.register_flight(flight_id, past_date, total_seats=100)
    
    # Assume reservation was created somehow validly before (or we are testing the payment check strictly)
    # However, creating reservation in past might also fail. 
    # Let's assume we mock a reservation that exists in CREATED state but time has passed.
    reservation = service._internal_create_reservation_bypass_checks(flight_id, seat=1)
    
    with pytest.raises(DomainException):
        service.confirm_payment(reservation.id, payment_approved=True)

# -------------------------------------------------------------------------
# STATE TRANSITIONS
# -------------------------------------------------------------------------

def test_invalid_transition_created_to_canceled(service, future_flight_date):
    """
    BR10 – The only valid state transitions are: CREATED → CONFIRMED, CONFIRMED → CANCELED.
    BR11 – Any state transition other than those defined must be rejected.
    
    Note: This explicitly validates that a CREATED reservation cannot be directly CANCELED 
    without being CONFIRMED first, per strict reading of BR10.
    """
    flight_id = "FL400"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    reservation = service.create_reservation(flight_id, seat=1)
    
    # Attempt CREATED -> CANCELED
    with pytest.raises(DomainException):
        service.cancel_reservation(reservation.id)
    
    updated_res = service.get_reservation(reservation.id)
    assert updated_res.state == ReservationState.CREATED

def test_invalid_transition_confirmed_to_created(service, future_flight_date):
    """
    BR10 – The only valid state transitions are: CREATED → CONFIRMED, CONFIRMED → CANCELED.
    BR11 – Any state transition other than those defined must be rejected.
    """
    flight_id = "FL401"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    reservation = service.create_reservation(flight_id, seat=1)
    service.confirm_payment(reservation.id, payment_approved=True)
    
    # Attempt rollback (logic not exposed in public API, but validating system integrity via payments)
    # Trying to pay again or "unconfirm" is impossible via API, verifying state persistence.
    current = service.get_reservation(reservation.id)
    assert current.state == ReservationState.CONFIRMED

# -------------------------------------------------------------------------
# CANCELLATION AND REFUNDS
# -------------------------------------------------------------------------

def test_cancel_reservation_full_refund(service):
    """
    BR05 – Canceled reservations must immediately release the associated seat.
    BR13 – Remaining time >= 24 hours before the flight → full refund.
    BR14 – Remaining time ... exact hours, with no rounding.
    FR04 – Cancel reservations while strictly respecting the refund policy.
    """
    # Flight exactly 25 hours from now
    flight_date = datetime.now() + timedelta(hours=25)
    flight_id = "FL500"
    
    service.register_flight(flight_id, flight_date, total_seats=100)
    res = service.create_reservation(flight_id, seat=1)
    service.confirm_payment(res.id, payment_approved=True)
    
    # Perform cancellation
    # Note: Service implementation usually returns refund details or logs it.
    # Since specific return type for refund isn't in Class Diagram, we assume 
    # method executes without error and strictly changes state.
    service.cancel_reservation(res.id)
    
    updated_res = service.get_reservation(res.id)
    assert updated_res.state == ReservationState.CANCELED
    
    # Verify seat release (BR05) - Another user should be able to book seat 1
    res2 = service.create_reservation(flight_id, seat=1)
    assert res2.state == ReservationState.CREATED
    assert res2.seat == 1

def test_cancel_reservation_no_refund_boundary(service):
    """
    BR13 – Remaining time < 24 hours before the flight → no refund.
    BR14 – Remaining time ... exact hours, with no rounding.
    """
    # Flight exactly 23 hours and 59 minutes from now
    flight_date = datetime.now() + timedelta(hours=23, minutes=59)
    flight_id = "FL501"
    
    service.register_flight(flight_id, flight_date, total_seats=100)
    res = service.create_reservation(flight_id, seat=1)
    service.confirm_payment(res.id, payment_approved=True)
    
    # This might return a specific status or void, but strictly,
    # the test validates the operation is allowed (state change)
    # The refund logic would be internal, but we ensure state is CANCELED.
    # If the system were to REJECT cancellation due to time, this test would change.
    # However, BR13 defines *refund policy*, not *cancellation prohibition*.
    service.cancel_reservation(res.id)
    
    updated_res = service.get_reservation(res.id)
    assert updated_res.state == ReservationState.CANCELED

def test_cancel_reservation_releases_seat_immediately(service, future_flight_date):
    """
    BR05 – Canceled reservations must immediately release the associated seat.
    """
    flight_id = "FL502"
    seat = 5
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    
    # User 1
    res1 = service.create_reservation(flight_id, seat)
    service.confirm_payment(res1.id, payment_approved=True)
    service.cancel_reservation(res1.id)
    
    # User 2 immediately takes the seat
    res2 = service.create_reservation(flight_id, seat)
    assert res2.seat == seat
    assert res2.state == ReservationState.CREATED

def test_canceled_reservation_is_immutable(service, future_flight_date):
    """
    BR12 – A canceled reservation must not be reactivated, modified, or receive new payments.
    BR20 – Payments must not be accepted for canceled reservations.
    """
    flight_id = "FL503"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    res = service.create_reservation(flight_id, seat=1)
    service.confirm_payment(res.id, payment_approved=True)
    service.cancel_reservation(res.id)
    
    # Attempt to pay again
    with pytest.raises(DomainException):
        service.confirm_payment(res.id, payment_approved=True)
        
    # Attempt to cancel again (Validation of state stability)
    with pytest.raises(DomainException):
        service.cancel_reservation(res.id)

# -------------------------------------------------------------------------
# IMMUTABILITY AND INTEGRITY
# -------------------------------------------------------------------------

def test_flight_data_immutability_after_confirmation(service, future_flight_date):
    """
    BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation.
    BR17 �� Indirect modifications of flight data are prohibited.
    FR05 – Prevent any invalid modification of state, flight data...
    """
    flight_id = "FL600"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    res = service.create_reservation(flight_id, seat=1)
    service.confirm_payment(res.id, payment_approved=True)
    
    # Attempt to modify flight time on the object associated with reservation
    # (Assuming implementation prevents this or we simulate attack vector)
    original_time = future_flight_date
    
    # Ideally, the system should not expose setters. 
    # If we access the internal flight object:
    flight = service.get_flight(flight_id)
    
    # If the system strictly follows BR17, this change should either raise exception
    # or be ignored/detached from the confirmed reservation.
    try:
        flight.dateTime = original_time + timedelta(hours=1)
    except AttributeError:
        pass # Immutability via strict object attributes
        
    # Re-fetch reservation to ensure it still points to original data logic
    # (Checking logical integrity)
    res_check = service.get_reservation(res.id)
    
    # The requirement is that the system uses "internally stored" data (BR15).
    # This test acts as a safeguard against mutable shared references.
    flight_check = service.get_flight_for_reservation(res_check.id)
    assert flight_check.dateTime == original_time

def test_operations_isolation(service, future_flight_date):
    """
    BR26 – Operations performed on one reservation must not affect other reservations.
    """
    flight_id = "FL700"
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    
    res1 = service.create_reservation(flight_id, seat=1)
    res2 = service.create_reservation(flight_id, seat=2)
    
    service.confirm_payment(res1.id, payment_approved=True)
    
    # Assert res2 is untouched
    assert service.get_reservation(res2.id).state == ReservationState.CREATED
    
    # Cancel res1
    service.cancel_reservation(res1.id)
    
    # Assert res2 is still untouched
    assert service.get_reservation(res2.id).state == ReservationState.CREATED
    
    # Confirm res2
    service.confirm_payment(res2.id, payment_approved=True)
    assert service.get_reservation(res2.id).state == ReservationState.CONFIRMED

def test_deterministic_behavior(service, future_flight_date):
    """
    BR21 – System operations must be deterministic, always producing the same result for the same inputs.
    """
    flight_id = "FL800"
    seat = 1
    service.register_flight(flight_id, future_flight_date, total_seats=100)
    
    # Sequence A
    res = service.create_reservation(flight_id, seat)
    assert res.seat == seat
    assert res.state == ReservationState.CREATED
    
    # Clean up (assuming service reset or new fixture usage for strict determinism)
    # In this test structure, we trust the 'service' fixture provides a clean slate.
    # We repeat the exact steps in a new service instance to prove determinism.
    
    from reservation_system import ReservationService
    service_b = ReservationService()
    service_b.register_flight(flight_id, future_flight_date, total_seats=100)
    
    res_b = service_b.create_reservation(flight_id, seat)
    assert res_b.seat == seat
    assert res_b.state == ReservationState.CREATED
    assert res.id != res_b.id # IDs distinct, but logic identical
```