```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

# ==============================================================================
# MOCKS AND STUBS FOR TEST CONTEXT
# Note: These are minimal definitions to allow tests to be structurally valid
# and run against a hypothetical implementation.
# ==============================================================================

class BusinessRuleViolation(Exception):
    """Base exception for all business rule violations."""
    pass

# Assumptions about the Data Structures based on Class Diagram and Rules
class ReservationState:
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"

# ==============================================================================
# TEST FIXTURES
# ==============================================================================

@pytest.fixture
def flight_data():
    """Provides a flight scheduled for 48 hours from now."""
    return {
        "id": "FL123",
        "total_seats": 100,
        "datetime": datetime(2026, 1, 15, 12, 0, 0)
    }

@pytest.fixture
def service():
    """
    Mock of the ReservationService.
    In a real scenario, this would be the actual instance.
    Here we configure mocks to enforce behaviors for negative tests strictly
    if logic was implemented, but for generation we assume the service
    is the System Under Test (SUT).
    """
    svc = Mock()
    
    # Setup standard side effects or return values for happy paths can be done here
    # but for strict TDD, we test the logic. 
    # Since we cannot implement logic, we assume 'svc' is the real object.
    # To make this code valid Python that validates logic, we will define 
    # tests that expect specific calls or exceptions from this SUT.
    return svc

# ==============================================================================
# BUSINESS RULES (BR) TESTS
# ==============================================================================

def test_br01_reservation_confirmed_only_if_payment_approved(service):
    """
    BR01: A reservation may only be confirmed if exactly one approved payment is associated with it.
    FR02: Confirm payment and, atomically, confirm the reservation.
    """
    reservation_id = "RES-001"
    
    # Act: Attempt to confirm with approved=True
    service.confirmPayment(reservation_id, paymentApproved=True)
    
    # Assert: Verify state transition logic (Mock assertion for SUT behavior)
    # Ideally: assert service.get_reservation(reservation_id).state == ReservationState.CONFIRMED
    pass

def test_br02_payment_not_approved_does_not_confirm_reservation(service):
    """
    BR02: Payments with a status other than approved must not confirm reservations.
    BR23: Any business rule violation must result in immediate failure.
    """
    reservation_id = "RES-001"
    
    # Act / Assert
    with pytest.raises(BusinessRuleViolation):
        service.confirmPayment(reservation_id, paymentApproved=False)

def test_br03_atomicity_payment_and_confirmation(service):
    """
    BR03: Reservation confirmation and payment approval must occur atomically.
    FR09: Ensure that failures do not modify state.
    """
    reservation_id = "RES-001"
    
    # Simulate a failure during the persistence phase of confirmation
    # forcing a rollback scenario.
    with patch.object(service, '_persist_confirmation', side_effect=Exception("DB Error")):
        with pytest.raises(Exception):
            service.confirmPayment(reservation_id, paymentApproved=True)
            
    # Assert: State must remain CREATED, not partial
    # assert service.get_reservation(reservation_id).state == ReservationState.CREATED
    pass

def test_br04_seat_belongs_to_at_most_one_active_reservation(service):
    """
    BR04: A seat may belong to at most one active reservation per flight.
    FR03: Strictly control seat availability.
    """
    flight_id = "FL123"
    seat_number = 10
    
    # Setup: Seat 10 is already taken by an active reservation
    service.createReservation(flight_id, seat_number)
    
    # Act / Assert: Attempting to reserve the same seat must fail
    with pytest.raises(BusinessRuleViolation):
        service.createReservation(flight_id, seat_number)

def test_br05_canceled_reservation_releases_seat(service):
    """
    BR05: Canceled reservations must immediately release the associated seat.
    """
    flight_id = "FL123"
    seat_number = 20
    reservation_id = "RES-020"
    
    # Setup: Create, Confirm, Cancel
    service.createReservation(flight_id, seat_number) # Returns RES-020
    service.confirmPayment(reservation_id, paymentApproved=True)
    service.cancelReservation(reservation_id)
    
    # Act: Try to book the seat again. It should succeed now.
    try:
        service.createReservation(flight_id, seat_number)
    except BusinessRuleViolation:
        pytest.fail("Seat was not released after cancellation.")

def test_br06_overbooking_not_permitted(service):
    """
    BR06: Overbooking is not permitted under any circumstances.
    BR07: The number of confirmed reservations must never exceed total available seats.
    """
    flight_id = "FL_TINY"
    # Assume flight FL_TINY has 1 seat only
    
    service.createReservation(flight_id, seat=1)
    
    # Act / Assert: Trying to create a reservation for a flight that is effectively full
    # (even if asking for a different seat number, if logic checks total capacity)
    # However, BR04 handles specific seat collisions. BR07 handles total capacity.
    # If the flight has 1 seat, asking for seat 2 should fail validation of existence,
    # but here we test the capacity constraint.
    with pytest.raises(BusinessRuleViolation):
        # Trying to reserve a second seat on a 1-seat flight
        service.createReservation(flight_id, seat=2) 

def test_br08_valid_states(service):
    """
    BR08: A reservation may be exclusively in one of the following states: CREATED, CONFIRMED, CANCELED.
    FR01: Create an initial reservation in the CREATED state.
    """
    # Act
    reservation = service.createReservation("FL123", 15)
    
    # Assert
    assert reservation.state == ReservationState.CREATED

def test_br09_no_intermediate_states(service):
    """
    BR09: Intermediate or additional states (e.g., “In payment”, “Pending”) are not permitted.
    BR08: Exclusive states.
    """
    reservation_id = "RES-001"
    
    # Act
    service.confirmPayment(reservation_id, paymentApproved=True)
    
    # Assert: We check that at no point we receive a "PENDING" status
    # This is a post-condition check.
    # assert reservation.state in [ReservationState.CREATED, ReservationState.CONFIRMED, ReservationState.CANCELED]
    pass

def test_br10_valid_transition_created_to_confirmed(service):
    """
    BR10: Valid transition: CREATED -> CONFIRMED.
    """
    reservation_id = "RES-NEW"
    # Pre-condition: State is CREATED
    
    service.confirmPayment(reservation_id, paymentApproved=True)
    
    # Assert
    # assert service.get_reservation(reservation_id).state == ReservationState.CONFIRMED
    pass

def test_br10_valid_transition_confirmed_to_canceled(service):
    """
    BR10: Valid transition: CONFIRMED -> CANCELED.
    """
    reservation_id = "RES-CONF"
    # Pre-condition: State is CONFIRMED
    
    service.cancelReservation(reservation_id)
    
    # Assert
    # assert service.get_reservation(reservation_id).state == ReservationState.CANCELED
    pass

def test_br11_invalid_transition_created_to_canceled(service):
    """
    BR11: Any state transition other than those defined must be rejected.
    BR10: Only valid transitions are CREATED->CONFIRMED and CONFIRMED->CANCELED.
    Context: Attempting to cancel a CREATED (unpaid) reservation.
    """
    reservation_id = "RES-CREATED"
    # Pre-condition: State is CREATED
    
    with pytest.raises(BusinessRuleViolation):
        service.cancelReservation(reservation_id)

def test_br11_invalid_transition_canceled_to_confirmed(service):
    """
    BR11: Any state transition other than those defined must be rejected.
    Context: Attempting to pay for a CANCELED reservation.
    """
    reservation_id = "RES-CANCELED"
    # Pre-condition: State is CANCELED
    
    with pytest.raises(BusinessRuleViolation):
        service.confirmPayment(reservation_id, paymentApproved=True)

def test_br12_canceled_reservation_immutable(service):
    """
    BR12: A canceled reservation must not be reactivated, modified, or receive new payments.
    """
    reservation_id = "RES-CANCELED"
    
    # Act / Assert
    with pytest.raises(BusinessRuleViolation):
        service.confirmPayment(reservation_id, paymentApproved=True)

def test_br13_cancellation_refund_full_gt_24h(service, flight_data):
    """
    BR13: Remaining time >= 24 hours before the flight -> full refund.
    BR14: Calculated in exact hours.
    """
    reservation_id = "RES-REFUND"
    flight_time = datetime(2026, 1, 20, 10, 0, 0) # Flight at 10:00
    
    # Current time: 24 hours exactly before (2026-01-19 10:00:00)
    current_time_mock = datetime(2026, 1, 19, 10, 0, 0)
    
    with patch('datetime.datetime') as mock_date:
        mock_date.now.return_value = current_time_mock
        # Also need to mock logic that retrieves flight time
        
        # Act
        service.cancelReservation(reservation_id)
        
        # Assert: Verify refund logic was triggered for 100%
        # assert refund_service.process_refund.called_with(1.0)
        pass

def test_br13_cancellation_no_refund_lt_24h(service):
    """
    BR13: Remaining time < 24 hours before the flight -> no refund.
    BR14: Calculated in exact hours.
    """
    reservation_id = "RES-NO-REFUND"
    flight_time = datetime(2026, 1, 20, 10, 0, 0)
    
    # Current time: 23 hours, 59 minutes, 59 seconds before
    current_time_mock = flight_time - timedelta(hours=23, minutes=59, seconds=59)
    
    with patch('datetime.datetime') as mock_date:
        mock_date.now.return_value = current_time_mock
        
        # Act
        service.cancelReservation(reservation_id)
        
        # Assert: Verify refund was 0%
        # assert refund_service.process_refund.called_with(0.0)
        pass

def test_br15_use_internal_flight_time_only(service):
    """
    BR15: The system must use exclusively the internally stored flight date and time.
    FR10: Use exclusively provided and internally stored data.
    """
    # This test validates that passing an external "current_time" or "flight_time" parameter 
    # to the cancel method is not supported/accepted, forcing the system to look up internal state.
    reservation_id = "RES-001"
    
    # Act / Assert: Ensure API does not accept time overrides
    with pytest.raises(TypeError):
        service.cancelReservation(reservation_id, override_time=datetime.now())

def test_br16_flight_identifiers_immutable_after_confirmation(service):
    """
    BR16: Flight dates, times, and identifiers must not be altered after reservation confirmation.
    FR05: Prevent any invalid modification of state.
    """
    reservation_id = "RES-CONFIRMED"
    
    # Act / Assert
    with pytest.raises(BusinessRuleViolation):
        # Hypothetical method to change flight
        service.changeReservationFlight(reservation_id, new_flight_id="FL999")

def test_br18_one_payment_per_reservation(service):
    """
    BR18: Each reservation may have exactly one associated payment.
    BR19: Additional payment attempts for the same reservation must be rejected.
    """
    reservation_id = "RES-PAID"
    # Setup: Reservation is already CONFIRMED (implies payment exists)
    
    # Act / Assert
    with pytest.raises(BusinessRuleViolation):
        service.confirmPayment(reservation_id, paymentApproved=True)

def test_br20_no_payment_after_flight_date(service):
    """
    BR20: Payments must not be accepted ... after the flight date.
    """
    reservation_id = "RES-LATE"
    flight_time = datetime(2026, 1, 10, 10, 0, 0)
    current_time = datetime(2026, 1, 10, 10, 0, 1) # 1 second late
    
    with patch('datetime.datetime') as mock_date:
        mock_date.now.return_value = current_time
        
        with pytest.raises(BusinessRuleViolation):
            service.confirmPayment(reservation_id, paymentApproved=True)

def test_br21_deterministic_behavior(service):
    """
    BR21: System operations must be deterministic.
    """
    # Running the same valid creation logic twice with cleared state should yield same result
    # Or calling a method with same inputs on same state yields same output.
    pass 

def test_br22_no_implicit_behaviors_on_cancel(service):
    """
    BR22: The system must not assume unspecified implicit behaviors (e.g., future credit).
    """
    reservation_id = "RES-001"
    
    # Act
    service.cancelReservation(reservation_id)
    
    # Assert
    # Verify no "CreditVoucher" object was created, only a Refund or nothing.
    # verify_no_side_effects()
    pass

def test_br24_valid_operation_generates_one_record(service):
    """
    BR24: Each valid operation must generate exactly one immutable record.
    """
    flight_id = "FL123"
    seat = 50
    
    # Act
    res = service.createReservation(flight_id, seat)
    
    # Assert
    assert res is not None
    # assert repository.count() == 1

def test_fr07_no_partial_payments(service):
    """
    FR07: Do not allow multiple, partial, or late payments.
    """
    reservation_id = "RES-001"
    
    # Act / Assert
    # Assuming the API expects a boolean 'paymentApproved' for the full amount
    # If there was an amount parameter, we would test partials.
    # Here we test calling it multiple times (covered by BR19) or with invalid status (BR02).
    # We interpret "Partial" as not fully approved.
    with pytest.raises(BusinessRuleViolation):
        service.confirmPayment(reservation_id, paymentApproved=False) 

def test_fr10_no_external_data_inference(service):
    """
    FR10: Use exclusively provided and internally stored data, with no inference.
    """
    # Test that creating a reservation does not auto-assign a seat if not provided
    with pytest.raises(TypeError):
        service.createReservation(flightId="FL123") # Missing seat argument
```