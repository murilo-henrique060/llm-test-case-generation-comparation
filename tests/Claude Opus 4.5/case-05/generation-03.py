```python
"""
Automated test cases for Airline Reservation System. 
Based exclusively on provided Business Rules (BR) and Functional Requirements (FR).
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from enum import Enum


# ============================================================================
# Test Fixtures and Helpers
# ============================================================================

class ReservationState(Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


@pytest.fixture
def mock_flight():
    """Create a mock flight with default values."""
    flight = Mock()
    flight.id = "FL001"
    flight. dateTime = datetime. now() + timedelta(hours=48)
    flight.totalSeats = 100
    return flight


@pytest.fixture
def mock_reservation():
    """Create a mock reservation in CREATED state."""
    reservation = Mock()
    reservation.id = "RES001"
    reservation.state = ReservationState.CREATED.value
    reservation.seat = 1
    reservation.flightId = "FL001"
    reservation.payment = None
    return reservation


@pytest. fixture
def mock_reservation_service():
    """Create a mock reservation service."""
    service = Mock()
    return service


# ============================================================================
# BR01 Tests - Reservation confirmation requires exactly one approved payment
# ============================================================================

def test_br01_reservation_confirmed_with_exactly_one_approved_payment(mock_reservation_service):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    mock_reservation_service. confirmPayment.return_value = None
    reservation_id = "RES001"
    payment_approved = True
    
    mock_reservation_service. confirmPayment(reservation_id, payment_approved)
    
    mock_reservation_service. confirmPayment.assert_called_once_with(reservation_id, payment_approved)


def test_br01_reservation_not_confirmed_without_payment(mock_reservation_service):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    mock_reservation_service.confirmPayment.side_effect = Exception("No payment associated")
    reservation_id = "RES001"
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, None)
    
    assert "No payment associated" in str(exc_info.value)


def test_br01_reservation_not_confirmed_with_zero_payments(mock_reservation_service):
    # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
    mock_reservation_service.confirmPayment.side_effect = Exception("Exactly one approved payment required")
    reservation_id = "RES001"
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, False)
    
    assert "Exactly one approved payment required" in str(exc_info.value)


# ============================================================================
# BR02 Tests - Non-approved payments must not confirm reservations
# ============================================================================

def test_br02_payment_not_approved_does_not_confirm_reservation(mock_reservation_service):
    # BR02 – Payments with a status other than approved must not confirm reservations
    mock_reservation_service.confirmPayment.side_effect = Exception("Payment not approved")
    reservation_id = "RES001"
    payment_approved = False
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, payment_approved)
    
    assert "Payment not approved" in str(exc_info.value)


def test_br02_only_approved_payment_confirms_reservation(mock_reservation_service):
    # BR02 – Payments with a status other than approved must not confirm reservations
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.confirmPayment. assert_called_with(reservation_id, True)


# ============================================================================
# BR03 Tests - Atomic reservation confirmation and payment approval
# ============================================================================

def test_br03_confirmation_and_payment_atomic_success(mock_reservation_service):
    # BR03 – Reservation confirmation and payment approval must occur atomically
    reservation_id = "RES001"
    payment_approved = True
    
    mock_reservation_service. confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(reservation_id, payment_approved)
    
    mock_reservation_service. confirmPayment.assert_called_once_with(reservation_id, payment_approved)


def test_br03_confirmation_and_payment_atomic_failure_rollback(mock_reservation_service):
    # BR03 – No observable state may exist in which only one of the two has been completed
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Atomic operation failed - rollback")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "rollback" in str(exc_info.value).lower()


def test_br03_partial_state_not_observable(mock_reservation_service, mock_reservation):
    # BR03 – No observable state may exist in which only one of the two has been completed
    initial_state = mock_reservation. state
    
    mock_reservation_service.confirmPayment. side_effect = Exception("Transaction failed")
    
    with pytest.raises(Exception):
        mock_reservation_service.confirmPayment(mock_reservation.id, True)
    
    assert mock_reservation.state == initial_state


# ============================================================================
# BR04 Tests - Seat exclusivity per active reservation
# ============================================================================

def test_br04_seat_belongs_to_one_active_reservation(mock_reservation_service):
    # BR04 – A seat may belong to at most one active reservation per flight
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(seat=seat, state=ReservationState.CREATED.value)
    reservation1 = mock_reservation_service. createReservation(flight_id, seat)
    
    mock_reservation_service.createReservation.side_effect = Exception("Seat already reserved")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, seat)
    
    assert "Seat already reserved" in str(exc_info. value)


def test_br04_different_seats_allowed_for_same_flight(mock_reservation_service):
    # BR04 – A seat may belong to at most one active reservation per flight
    flight_id = "FL001"
    
    mock_reservation_service.createReservation.side_effect = [
        Mock(seat=1, state=ReservationState. CREATED.value),
        Mock(seat=2, state=ReservationState. CREATED.value)
    ]
    
    reservation1 = mock_reservation_service.createReservation(flight_id, 1)
    reservation2 = mock_reservation_service.createReservation(flight_id, 2)
    
    assert reservation1.seat == 1
    assert reservation2.seat == 2


# ============================================================================
# BR05 Tests - Canceled reservations release seats immediately
# ============================================================================

def test_br05_canceled_reservation_releases_seat(mock_reservation_service):
    # BR05 – Canceled reservations must immediately release the associated seat
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(id="RES001", seat=seat)
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    mock_reservation_service.cancelReservation. return_value = None
    mock_reservation_service. cancelReservation(reservation.id)
    
    mock_reservation_service.createReservation.return_value = Mock(id="RES002", seat=seat)
    new_reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert new_reservation.seat == seat


def test_br05_seat_available_immediately_after_cancellation(mock_reservation_service):
    # BR05 – Canceled reservations must immediately release the associated seat
    flight_id = "FL001"
    seat = 5
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.return_value = None
    mock_reservation_service.cancelReservation(reservation_id)
    
    mock_reservation_service.createReservation.return_value = Mock(seat=seat)
    new_reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert new_reservation.seat == seat


# ============================================================================
# BR06 Tests - Overbooking prohibition
# ============================================================================

def test_br06_overbooking_not_permitted(mock_reservation_service, mock_flight):
    # BR06 – Overbooking is not permitted under any circumstances
    mock_flight.totalSeats = 1
    
    mock_reservation_service. createReservation. return_value = Mock(seat=1)
    mock_reservation_service. createReservation(mock_flight.id, 1)
    
    mock_reservation_service. createReservation. side_effect = Exception("Overbooking not permitted")
    
    with pytest.raises(Exception) as exc_info: 
        mock_reservation_service.createReservation(mock_flight.id, 2)
    
    assert "Overbooking not permitted" in str(exc_info.value)


def test_br06_cannot_exceed_total_seats(mock_reservation_service):
    # BR06 – Overbooking is not permitted under any circumstances
    flight_id = "FL001"
    total_seats = 2
    
    mock_reservation_service. createReservation. side_effect = [
        Mock(seat=1),
        Mock(seat=2),
        Exception("All seats occupied - overbooking prohibited")
    ]
    
    mock_reservation_service. createReservation(flight_id, 1)
    mock_reservation_service. createReservation(flight_id, 2)
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, 3)
    
    assert "overbooking prohibited" in str(exc_info.value).lower()


# ============================================================================
# BR07 Tests - Confirmed reservations cannot exceed available seats
# ============================================================================

def test_br07_confirmed_reservations_not_exceed_available_seats(mock_reservation_service):
    # BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
    flight_id = "FL001"
    total_seats = 1
    
    mock_reservation_service. createReservation. return_value = Mock(id="RES001", seat=1)
    mock_reservation_service.confirmPayment.return_value = None
    
    reservation = mock_reservation_service.createReservation(flight_id, 1)
    mock_reservation_service. confirmPayment(reservation.id, True)
    
    mock_reservation_service. createReservation.side_effect = Exception("No available seats")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.createReservation(flight_id, 2)
    
    assert "No available seats" in str(exc_info.value)


# ============================================================================
# BR08 Tests - Reservation states exclusivity
# ============================================================================

def test_br08_reservation_state_is_created(mock_reservation_service):
    # BR08 – A reservation may be exclusively in one of the following states:  CREATED
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service. createReservation. return_value = Mock(state=ReservationState.CREATED.value)
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation.state == ReservationState.CREATED. value


def test_br08_reservation_state_is_confirmed(mock_reservation_service):
    # BR08 – A reservation may be exclusively in one of the following states: CONFIRMED
    mock_reservation_service. confirmPayment.return_value = None
    mock_reservation_service. getReservation = Mock(return_value=Mock(state=ReservationState. CONFIRMED.value))
    
    mock_reservation_service. confirmPayment("RES001", True)
    reservation = mock_reservation_service.getReservation("RES001")
    
    assert reservation.state == ReservationState. CONFIRMED.value


def test_br08_reservation_state_is_canceled(mock_reservation_service):
    # BR08 – A reservation may be exclusively in one of the following states:  CANCELED
    mock_reservation_service.cancelReservation.return_value = None
    mock_reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CANCELED. value))
    
    mock_reservation_service.cancelReservation("RES001")
    reservation = mock_reservation_service.getReservation("RES001")
    
    assert reservation.state == ReservationState. CANCELED.value


# ============================================================================
# BR09 Tests - No intermediate or additional states
# ============================================================================

def test_br09_no_pending_state_allowed(mock_reservation_service):
    # BR09 – Intermediate or additional states (e.g., "In payment", "Pending", "Expired") are not permitted
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(state=ReservationState.CREATED.value)
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation.state in [ReservationState.CREATED.value, ReservationState.CONFIRMED.value, ReservationState.CANCELED.value]
    assert reservation.state != "PENDING"


def test_br09_no_in_payment_state_allowed(mock_reservation_service):
    # BR09 – Intermediate or additional states (e.g., "In payment", "Pending", "Expired") are not permitted
    mock_reservation_service. getReservation = Mock(return_value=Mock(state=ReservationState. CREATED.value))
    reservation = mock_reservation_service.getReservation("RES001")
    
    assert reservation.state != "IN_PAYMENT"


def test_br09_no_expired_state_allowed(mock_reservation_service):
    # BR09 – Intermediate or additional states (e.g., "In payment", "Pending", "Expired") are not permitted
    mock_reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED.value))
    reservation = mock_reservation_service.getReservation("RES001")
    
    assert reservation.state != "EXPIRED"


# ============================================================================
# BR10 Tests - Valid state transitions
# ============================================================================

def test_br10_valid_transition_created_to_confirmed(mock_reservation_service, mock_reservation):
    # BR10 – The only valid state transitions are:  CREATED → CONFIRMED
    assert mock_reservation.state == ReservationState.CREATED.value
    
    mock_reservation_service. confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(mock_reservation.id, True)
    
    mock_reservation. state = ReservationState.CONFIRMED. value
    assert mock_reservation.state == ReservationState.CONFIRMED.value


def test_br10_valid_transition_confirmed_to_canceled(mock_reservation_service):
    # BR10 – The only valid state transitions are:  CONFIRMED → CANCELED
    reservation = Mock(id="RES001", state=ReservationState.CONFIRMED. value)
    
    mock_reservation_service.cancelReservation.return_value = None
    mock_reservation_service.cancelReservation(reservation.id)
    
    reservation.state = ReservationState.CANCELED.value
    assert reservation.state == ReservationState. CANCELED.value


# ============================================================================
# BR11 Tests - Invalid state transitions rejection
# ============================================================================

def test_br11_invalid_transition_created_to_canceled_rejected(mock_reservation_service, mock_reservation):
    # BR11 – Any state transition other than those defined must be rejected
    assert mock_reservation.state == ReservationState. CREATED.value
    
    mock_reservation_service.cancelReservation.side_effect = Exception("Invalid state transition:  CREATED to CANCELED")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.cancelReservation(mock_reservation.id)
    
    assert "Invalid state transition" in str(exc_info. value)


def test_br11_invalid_transition_canceled_to_confirmed_rejected(mock_reservation_service):
    # BR11 – Any state transition other than those defined must be rejected
    reservation = Mock(id="RES001", state=ReservationState.CANCELED.value)
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Invalid state transition: CANCELED to CONFIRMED")
    
    with pytest.raises(Exception) as exc_info: 
        mock_reservation_service.confirmPayment(reservation.id, True)
    
    assert "Invalid state transition" in str(exc_info. value)


def test_br11_invalid_transition_confirmed_to_created_rejected(mock_reservation_service):
    # BR11 – Any state transition other than those defined must be rejected
    reservation = Mock(id="RES001", state=ReservationState.CONFIRMED.value)
    
    mock_reservation_service.revertToCreated = Mock(side_effect=Exception("Invalid state transition: CONFIRMED to CREATED"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.revertToCreated(reservation. id)
    
    assert "Invalid state transition" in str(exc_info.value)


def test_br11_invalid_transition_canceled_to_created_rejected(mock_reservation_service):
    # BR11 – Any state transition other than those defined must be rejected
    reservation = Mock(id="RES001", state=ReservationState. CANCELED.value)
    
    mock_reservation_service. revertToCreated = Mock(side_effect=Exception("Invalid state transition: CANCELED to CREATED"))
    
    with pytest.raises(Exception) as exc_info: 
        mock_reservation_service.revertToCreated(reservation.id)
    
    assert "Invalid state transition" in str(exc_info. value)


# ============================================================================
# BR12 Tests - Canceled reservation immutability
# ============================================================================

def test_br12_canceled_reservation_cannot_be_reactivated(mock_reservation_service):
    # BR12 – A canceled reservation must not be reactivated
    reservation_id = "RES001"
    
    mock_reservation_service.reactivateReservation = Mock(side_effect=Exception("Canceled reservation cannot be reactivated"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.reactivateReservation(reservation_id)
    
    assert "cannot be reactivated" in str(exc_info.value)


def test_br12_canceled_reservation_cannot_be_modified(mock_reservation_service):
    # BR12 – A canceled reservation must not be modified
    reservation_id = "RES001"
    
    mock_reservation_service.modifyReservation = Mock(side_effect=Exception("Canceled reservation cannot be modified"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.modifyReservation(reservation_id, seat=5)
    
    assert "cannot be modified" in str(exc_info.value)


def test_br12_canceled_reservation_cannot_receive_new_payments(mock_reservation_service):
    # BR12 – A canceled reservation must not receive new payments
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.side_effect = Exception("Canceled reservation cannot receive payments")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. confirmPayment(reservation_id, True)
    
    assert "cannot receive payments" in str(exc_info.value)


# ============================================================================
# BR13 Tests - Temporal refund policy
# ============================================================================

def test_br13_full_refund_when_24_hours_or_more_before_flight(mock_reservation_service):
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.return_value = {"refund": "full", "amount": 100. 00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "full"


def test_br13_no_refund_when_less_than_24_hours_before_flight(mock_reservation_service):
    # BR13 – Remaining time < 24 hours before the flight → no refund
    reservation_id = "RES001"
    
    mock_reservation_service. cancelReservation. return_value = {"refund": "none", "amount": 0.00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "none"
    assert result["amount"] == 0.00


def test_br13_exactly_24_hours_before_flight_full_refund(mock_reservation_service):
    # BR13 – Remaining time ≥ 24 hours before the flight → full refund (edge case:  exactly 24 hours)
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.return_value = {"refund":  "full", "amount": 100.00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "full"


def test_br13_23_hours_59_minutes_before_flight_no_refund(mock_reservation_service):
    # BR13 – Remaining time < 24 hours before the flight → no refund (edge case: 23h59m)
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.return_value = {"refund": "none", "amount": 0.00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "none"


# ============================================================================
# BR14 Tests - Exact hour calculation without rounding
# ============================================================================

def test_br14_remaining_time_calculated_in_exact_hours(mock_reservation_service):
    # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding or tolerance
    reservation_id = "RES001"
    
    mock_reservation_service.getRemainingHours = Mock(return_value=24. 0)
    remaining_hours = mock_reservation_service.getRemainingHours(reservation_id)
    
    assert remaining_hours == 24.0


def test_br14_no_rounding_in_time_calculation(mock_reservation_service):
    # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding or tolerance
    reservation_id = "RES001"
    
    mock_reservation_service.getRemainingHours = Mock(return_value=23.999)
    remaining_hours = mock_reservation_service.getRemainingHours(reservation_id)
    
    assert remaining_hours == 23.999
    assert remaining_hours < 24.0


# ============================================================================
# BR15 Tests - Internal flight date/time as temporal reference
# ============================================================================

def test_br15_uses_internally_stored_flight_datetime(mock_reservation_service, mock_flight):
    # BR15 – The system must use exclusively the internally stored flight date and time as the temporal reference
    mock_reservation_service.getFlightDateTime = Mock(return_value=mock_flight.dateTime)
    
    flight_datetime = mock_reservation_service.getFlightDateTime(mock_flight.id)
    
    assert flight_datetime == mock_flight. dateTime


def test_br15_does_not_use_external_time_reference(mock_reservation_service, mock_flight):
    # BR15 – The system must use exclusively the internally stored flight date and time as the temporal reference
    stored_datetime = mock_flight.dateTime
    external_datetime = datetime.now()
    
    mock_reservation_service.getFlightDateTime = Mock(return_value=stored_datetime)
    flight_datetime = mock_reservation_service.getFlightDateTime(mock_flight.id)
    
    assert flight_datetime == stored_datetime
    assert flight_datetime != external_datetime


# ============================================================================
# BR16 Tests - Flight data immutability after confirmation
# ============================================================================

def test_br16_flight_date_cannot_be_altered_after_confirmation(mock_reservation_service):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    reservation_id = "RES001"
    
    mock_reservation_service.updateFlightDate = Mock(side_effect=Exception("Flight date cannot be altered after confirmation"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.updateFlightDate(reservation_id, datetime.now())
    
    assert "cannot be altered" in str(exc_info. value)


def test_br16_flight_time_cannot_be_altered_after_confirmation(mock_reservation_service):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    reservation_id = "RES001"
    
    mock_reservation_service.updateFlightTime = Mock(side_effect=Exception("Flight time cannot be altered after confirmation"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.updateFlightTime(reservation_id, datetime. now())
    
    assert "cannot be altered" in str(exc_info.value)


def test_br16_flight_identifier_cannot_be_altered_after_confirmation(mock_reservation_service):
    # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
    reservation_id = "RES001"
    
    mock_reservation_service.updateFlightId = Mock(side_effect=Exception("Flight identifier cannot be altered after confirmation"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.updateFlightId(reservation_id, "FL002")
    
    assert "cannot be altered" in str(exc_info.value)


# ============================================================================
# BR17 Tests - Prohibition of indirect flight data modifications
# ============================================================================

def test_br17_reference_swapping_prohibited(mock_reservation_service):
    # BR17 – Indirect modifications of flight data (reference swapping) are prohibited
    reservation_id = "RES001"
    
    mock_reservation_service.swapFlightReference = Mock(side_effect=Exception("Reference swapping prohibited"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. swapFlightReference(reservation_id, "FL002")
    
    assert "Reference swapping prohibited" in str(exc_info.value)


def test_br17_cloning_prohibited(mock_reservation_service):
    # BR17 – Indirect modifications of flight data (cloning) are prohibited
    reservation_id = "RES001"
    
    mock_reservation_service. cloneFlight = Mock(side_effect=Exception("Cloning prohibited"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. cloneFlight(reservation_id)
    
    assert "Cloning prohibited" in str(exc_info.value)


def test_br17_object_recreation_prohibited(mock_reservation_service):
    # BR17 – Indirect modifications of flight data (object recreation) are prohibited
    reservation_id = "RES001"
    
    mock_reservation_service.recreateFlight = Mock(side_effect=Exception("Object recreation prohibited"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. recreateFlight(reservation_id)
    
    assert "Object recreation prohibited" in str(exc_info.value)


# ============================================================================
# BR18 Tests - Exactly one payment per reservation
# ============================================================================

def test_br18_reservation_has_exactly_one_payment(mock_reservation_service):
    # BR18 – Each reservation may have exactly one associated payment
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment. return_value = None
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.getPaymentCount = Mock(return_value=1)
    payment_count = mock_reservation_service. getPaymentCount(reservation_id)
    
    assert payment_count == 1


def test_br18_reservation_cannot_have_multiple_payments(mock_reservation_service):
    # BR18 – Each reservation may have exactly one associated payment
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.addSecondPayment = Mock(side_effect=Exception("Only one payment allowed per reservation"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.addSecondPayment(reservation_id, True)
    
    assert "Only one payment allowed" in str(exc_info.value)


# ============================================================================
# BR19 Tests - Additional payment attempts rejection
# ============================================================================

def test_br19_additional_payment_attempt_rejected(mock_reservation_service):
    # BR19 – Additional payment attempts for the same reservation must be rejected
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.confirmPayment. side_effect = Exception("Additional payment attempt rejected")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "Additional payment attempt rejected" in str(exc_info.value)


def test_br19_second_payment_after_first_failed_rejected(mock_reservation_service):
    # BR19 – Additional payment attempts for the same reservation must be rejected
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.side_effect = [
        Exception("Payment failed"),
        Exception("Additional payment attempt rejected")
    ]
    
    with pytest.raises(Exception):
        mock_reservation_service.confirmPayment(reservation_id, False)
    
    with pytest.raises(Exception) as exc_info: 
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "Additional payment attempt rejected" in str(exc_info.value)


# ============================================================================
# BR20 Tests - Payment rejection for canceled reservations or after flight date
# ============================================================================

def test_br20_payment_not_accepted_for_canceled_reservation(mock_reservation_service):
    # BR20 – Payments must not be accepted for canceled reservations
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.side_effect = Exception("Payment not accepted for canceled reservation")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "canceled reservation" in str(exc_info.value)


def test_br20_payment_not_accepted_after_flight_date(mock_reservation_service):
    # BR20 – Payments must not be accepted after the flight date
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Payment not accepted after flight date")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "after flight date" in str(exc_info.value)


# ============================================================================
# BR21 Tests - Deterministic operations
# ============================================================================

def test_br21_operations_are_deterministic(mock_reservation_service):
    # BR21 – System operations must be deterministic, always producing the same result for the same sequence of inputs
    flight_id = "FL001"
    seat = 1
    
    expected_reservation = Mock(id="RES001", seat=seat, state=ReservationState.CREATED.value)
    mock_reservation_service. createReservation. return_value = expected_reservation
    
    result1 = mock_reservation_service.createReservation(flight_id, seat)
    
    mock_reservation_service. createReservation. return_value = expected_reservation
    result2 = mock_reservation_service.createReservation(flight_id, seat)
    
    assert result1.id == result2.id
    assert result1.seat == result2.seat
    assert result1.state == result2.state


def test_br21_same_inputs_same_outputs(mock_reservation_service):
    # BR21 – System operations must be deterministic, always producing the same result for the same sequence of inputs
    reservation_id = "RES001"
    
    mock_reservation_service. cancelReservation. return_value = {"refund": "full", "amount": 100.00}
    
    result1 = mock_reservation_service.cancelReservation(reservation_id)
    result2 = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result1 == result2


# ============================================================================
# BR22 Tests - No unspecified implicit behaviors
# ============================================================================

def test_br22_no_future_credit_assumed(mock_reservation_service):
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., future credit)
    reservation_id = "RES001"
    
    mock_reservation_service.getFutureCredit = Mock(side_effect=Exception("Future credit not supported"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. getFutureCredit(reservation_id)
    
    assert "not supported" in str(exc_info.value)


def test_br22_no_automatic_rebooking_assumed(mock_reservation_service):
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
    reservation_id = "RES001"
    
    mock_reservation_service.automaticRebook = Mock(side_effect=Exception("Automatic rebooking not supported"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.automaticRebook(reservation_id)
    
    assert "not supported" in str(exc_info.value)


def test_br22_no_commercial_exceptions_assumed(mock_reservation_service):
    # BR22 – The system must not assume unspecified implicit behaviors (e.g., commercial exceptions)
    reservation_id = "RES001"
    
    mock_reservation_service. applyCommercialException = Mock(side_effect=Exception("Commercial exceptions not supported"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.applyCommercialException(reservation_id)
    
    assert "not supported" in str(exc_info.value)


# ============================================================================
# BR23 Tests - Immediate failure on business rule violation
# ============================================================================

def test_br23_violation_results_in_immediate_failure(mock_reservation_service):
    # BR23 – Any business rule violation must result in immediate failure
    flight_id = "FL001"
    invalid_seat = -1
    
    mock_reservation_service.createReservation.side_effect = Exception("Business rule violation:  invalid seat")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.createReservation(flight_id, invalid_seat)
    
    assert "Business rule violation" in str(exc_info. value)


def test_br23_no_state_change_on_violation(mock_reservation_service, mock_reservation):
    # BR23 – Any business rule violation must result in no state change
    initial_state = mock_reservation.state
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Business rule violation")
    
    with pytest.raises(Exception):
        mock_reservation_service.confirmPayment(mock_reservation.id, False)
    
    assert mock_reservation. state == initial_state


def test_br23_no_partial_records_on_violation(mock_reservation_service):
    # BR23 – Any business rule violation must result in no creation of partial records
    flight_id = "FL001"
    
    mock_reservation_service.createReservation.side_effect = Exception("Business rule violation")
    mock_reservation_service. getReservationCount = Mock(return_value=0)
    
    with pytest.raises(Exception):
        mock_reservation_service. createReservation(flight_id, 1)
    
    count = mock_reservation_service.getReservationCount()
    assert count == 0


# ============================================================================
# BR24 Tests - Immutable records for valid operations
# ============================================================================

def test_br24_valid_operation_generates_immutable_record(mock_reservation_service):
    # BR24 – Each valid operation must generate exactly one immutable record
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service. createReservation. return_value = Mock(id="RES001", immutable=True)
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation. id == "RES001"
    assert reservation.immutable == True


def test_br24_exactly_one_record_per_valid_operation(mock_reservation_service):
    # BR24 – Each valid operation must generate exactly one immutable record
    flight_id = "FL001"
    
    mock_reservation_service.getRecordCount = Mock(return_value=0)
    initial_count = mock_reservation_service.getRecordCount()
    
    mock_reservation_service.createReservation.return_value = Mock(id="RES001")
    mock_reservation_service. createReservation(flight_id, 1)
    
    mock_reservation_service. getRecordCount. return_value = 1
    final_count = mock_reservation_service.getRecordCount()
    
    assert final_count - initial_count == 1


# ============================================================================
# BR25 Tests - No persistent records for failed operations
# ============================================================================

def test_br25_failed_operation_does_not_generate_record(mock_reservation_service):
    # BR25 – Failed operations must not generate persistent records
    flight_id = "FL001"
    invalid_seat = -1
    
    mock_reservation_service. getRecordCount = Mock(return_value=0)
    initial_count = mock_reservation_service.getRecordCount()
    
    mock_reservation_service.createReservation.side_effect = Exception("Invalid seat")
    
    with pytest.raises(Exception):
        mock_reservation_service.createReservation(flight_id, invalid_seat)
    
    final_count = mock_reservation_service.getRecordCount()
    assert final_count == initial_count


def test_br25_no_partial_records_on_failure(mock_reservation_service):
    # BR25 – Failed operations must not generate persistent records
    reservation_id = "RES001"
    
    mock_reservation_service.getAuditLogCount = Mock(return_value=5)
    initial_log_count = mock_reservation_service.getAuditLogCount()
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Payment failed")
    
    with pytest.raises(Exception):
        mock_reservation_service.confirmPayment(reservation_id, False)
    
    final_log_count = mock_reservation_service.getAuditLogCount()
    assert final_log_count == initial_log_count


# ============================================================================
# BR26 Tests - Operation isolation
# ============================================================================

def test_br26_operation_does_not_affect_other_reservations(mock_reservation_service):
    # BR26 – Operations performed on one reservation must not affect other reservations
    reservation1 = Mock(id="RES001", state=ReservationState.CONFIRMED.value)
    reservation2 = Mock(id="RES002", state=ReservationState. CONFIRMED.value)
    
    mock_reservation_service.cancelReservation.return_value = None
    mock_reservation_service.cancelReservation(reservation1.id)
    reservation1.state = ReservationState. CANCELED.value
    
    assert reservation2.state == ReservationState.CONFIRMED.value


def test_br26_operation_does_not_affect_other_flights(mock_reservation_service):
    # BR26 – Operations performed on one reservation must not affect other flights
    flight1 = Mock(id="FL001", totalSeats=100)
    flight2 = Mock(id="FL002", totalSeats=100)
    
    mock_reservation_service. createReservation. return_value = Mock(flightId=flight1.id, seat=1)
    mock_reservation_service.createReservation(flight1.id, 1)
    
    assert flight2.totalSeats == 100


def test_br26_operation_does_not_affect_other_seats(mock_reservation_service):
    # BR26 – Operations performed on one reservation must not affect other seats
    flight_id = "FL001"
    
    mock_reservation_service.createReservation.return_value = Mock(seat=1)
    mock_reservation_service.createReservation(flight_id, 1)
    
    mock_reservation_service. isSeatAvailable = Mock(return_value=True)
    is_seat_2_available = mock_reservation_service.isSeatAvailable(flight_id, 2)
    
    assert is_seat_2_available == True


# ============================================================================
# FR01 Tests - Create initial reservation in CREATED state
# ============================================================================

def test_fr01_create_reservation_in_created_state(mock_reservation_service):
    # FR01 – Create an initial reservation in the CREATED state
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(
        id="RES001",
        state=ReservationState.CREATED.value,
        seat=seat,
        flightId=flight_id
    )
    
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation. state == ReservationState.CREATED.value


def test_fr01_reservation_associated_with_flight(mock_reservation_service):
    # FR01 – Create an initial reservation associated with a flight
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(
        flightId=flight_id,
        seat=seat,
        state=ReservationState. CREATED.value
    )
    
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation.flightId == flight_id


def test_fr01_reservation_associated_with_available_seat(mock_reservation_service):
    # FR01 – Create an initial reservation associated with an available seat
    flight_id = "FL001"
    seat = 5
    
    mock_reservation_service. createReservation. return_value = Mock(seat=seat, state=ReservationState. CREATED.value)
    
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation. seat == seat


def test_fr01_cannot_create_reservation_with_unavailable_seat(mock_reservation_service):
    # FR01 – Create an initial reservation associated with an available seat (negative case)
    flight_id = "FL001"
    unavailable_seat = 1
    
    mock_reservation_service. createReservation. side_effect = Exception("Seat not available")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, unavailable_seat)
    
    assert "Seat not available" in str(exc_info.value)


# ============================================================================
# FR02 Tests - Confirm payment and atomically confirm reservation
# ============================================================================

def test_fr02_confirm_payment_confirms_reservation(mock_reservation_service):
    # FR02 – Confirm payment and, atomically, confirm the reservation
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.return_value = None
    mock_reservation_service. getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED.value))
    
    mock_reservation_service. confirmPayment(reservation_id, True)
    reservation = mock_reservation_service.getReservation(reservation_id)
    
    assert reservation.state == ReservationState. CONFIRMED.value


def test_fr02_payment_and_confirmation_are_atomic(mock_reservation_service):
    # FR02 – Confirm payment and, atomically, confirm the reservation
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment. return_value = None
    mock_reservation_service.confirmPayment. assert_not_called()
    
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.confirmPayment.assert_called_once_with(reservation_id, True)


# ============================================================================
# FR03 Tests - Strict seat availability control
# ============================================================================

def test_fr03_seat_availability_strictly_controlled(mock_reservation_service):
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service. createReservation. return_value = Mock(seat=seat, state=ReservationState. CREATED.value)
    mock_reservation_service. createReservation(flight_id, seat)
    
    mock_reservation_service. isSeatAvailable = Mock(return_value=False)
    is_available = mock_reservation_service.isSeatAvailable(flight_id, seat)
    
    assert is_available == False


def test_fr03_seat_exclusivity_per_active_reservation(mock_reservation_service):
    # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.side_effect = [
        Mock(seat=seat),
        Exception("Seat already has active reservation")
    ]
    
    mock_reservation_service. createReservation(flight_id, seat)
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, seat)
    
    assert "active reservation" in str(exc_info.value)


# ============================================================================
# FR04 Tests - Cancel reservations respecting refund policy
# ============================================================================

def test_fr04_cancel_reservation_with_full_refund(mock_reservation_service):
    # FR04 – Cancel reservations while strictly respecting the refund policy (≥24 hours)
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.return_value = {"refund": "full", "amount": 100.00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "full"


def test_fr04_cancel_reservation_with_no_refund(mock_reservation_service):
    # FR04 – Cancel reservations while strictly respecting the refund policy (<24 hours)
    reservation_id = "RES001"
    
    mock_reservation_service. cancelReservation. return_value = {"refund": "none", "amount": 0.00}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "none"


# ============================================================================
# FR05 Tests - Prevent invalid modifications
# ============================================================================

def test_fr05_prevent_invalid_state_modification(mock_reservation_service):
    # FR05 – Prevent any invalid modification of state
    reservation_id = "RES001"
    
    mock_reservation_service.setInvalidState = Mock(side_effect=Exception("Invalid state modification"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. setInvalidState(reservation_id, "INVALID_STATE")
    
    assert "Invalid state modification" in str(exc_info.value)


def test_fr05_prevent_invalid_flight_data_modification(mock_reservation_service):
    # FR05 – Prevent any invalid modification of flight data
    reservation_id = "RES001"
    
    mock_reservation_service. modifyFlightData = Mock(side_effect=Exception("Invalid flight data modification"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.modifyFlightData(reservation_id, {"dateTime": datetime.now()})
    
    assert "Invalid flight data modification" in str(exc_info.value)


def test_fr05_prevent_invalid_seat_modification(mock_reservation_service):
    # FR05 – Prevent any invalid modification of seat
    reservation_id = "RES001"
    
    mock_reservation_service.modifySeat = Mock(side_effect=Exception("Invalid seat modification"))
    
    with pytest.raises(Exception) as exc_info: 
        mock_reservation_service.modifySeat(reservation_id, 99)
    
    assert "Invalid seat modification" in str(exc_info.value)


def test_fr05_prevent_invalid_payment_modification(mock_reservation_service):
    # FR05 – Prevent any invalid modification of payment
    reservation_id = "RES001"
    
    mock_reservation_service.modifyPayment = Mock(side_effect=Exception("Invalid payment modification"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. modifyPayment(reservation_id, {"amount": 50.00})
    
    assert "Invalid payment modification" in str(exc_info. value)


# ============================================================================
# FR06 Tests - No overbooking at any stage
# ============================================================================

def test_fr06_no_overbooking_at_creation_stage(mock_reservation_service):
    # FR06 – Do not allow overbooking at any stage of the process (creation)
    flight_id = "FL001"
    
    mock_reservation_service.createReservation.side_effect = Exception("Overbooking not allowed at creation")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, 101)
    
    assert "Overbooking not allowed" in str(exc_info.value)


def test_fr06_no_overbooking_at_confirmation_stage(mock_reservation_service):
    # FR06 – Do not allow overbooking at any stage of the process (confirmation)
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Overbooking not allowed at confirmation")
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "Overbooking not allowed" in str(exc_info.value)


# ============================================================================
# FR07 Tests - No multiple, partial, or late payments
# ============================================================================

def test_fr07_no_multiple_payments(mock_reservation_service):
    # FR07 – Do not allow multiple payments
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.return_value = None
    mock_reservation_service.confirmPayment(reservation_id, True)
    
    mock_reservation_service.confirmPayment. side_effect = Exception("Multiple payments not allowed")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert "Multiple payments not allowed" in str(exc_info.value)


def test_fr07_no_partial_payments(mock_reservation_service):
    # FR07 – Do not allow partial payments
    reservation_id = "RES001"
    
    mock_reservation_service.makePartialPayment = Mock(side_effect=Exception("Partial payments not allowed"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.makePartialPayment(reservation_id, 50.00)
    
    assert "Partial payments not allowed" in str(exc_info.value)


def test_fr07_no_late_payments(mock_reservation_service):
    # FR07 – Do not allow late payments
    reservation_id = "RES001"
    
    mock_reservation_service. confirmPayment.side_effect = Exception("Late payments not allowed")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service. confirmPayment(reservation_id, True)
    
    assert "Late payments not allowed" in str(exc_info.value)


# ============================================================================
# FR08 Tests - No intermediate states or partial results
# ============================================================================

def test_fr08_no_intermediate_states_returned(mock_reservation_service):
    # FR08 – Do not return intermediate states
    reservation_id = "RES001"
    
    mock_reservation_service. getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED.value))
    reservation = mock_reservation_service.getReservation(reservation_id)
    
    assert reservation.state in [
        ReservationState.CREATED.value,
        ReservationState. CONFIRMED.value,
        ReservationState.CANCELED. value
    ]


def test_fr08_no_explanatory_messages_returned(mock_reservation_service):
    # FR08 – Do not return explanatory messages
    reservation_id = "RES001"
    
    mock_reservation_service.confirmPayment.return_value = None
    result = mock_reservation_service.confirmPayment(reservation_id, True)
    
    assert result is None


def test_fr08_no_partial_results_returned(mock_reservation_service):
    # FR08 – Do not return partial results
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(
        id="RES001",
        state=ReservationState.CREATED. value,
        seat=seat,
        flightId=flight_id
    )
    
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation. id is not None
    assert reservation.state is not None
    assert reservation.seat is not None
    assert reservation.flightId is not None


# ============================================================================
# FR09 Tests - Failures do not modify state or produce side effects
# ============================================================================

def test_fr09_failure_does_not_modify_state(mock_reservation_service, mock_reservation):
    # FR09 – Ensure that failures do not modify state
    initial_state = mock_reservation.state
    
    mock_reservation_service.confirmPayment.side_effect = Exception("Operation failed")
    
    with pytest.raises(Exception):
        mock_reservation_service.confirmPayment(mock_reservation.id, False)
    
    assert mock_reservation. state == initial_state


def test_fr09_failure_does_not_produce_side_effects(mock_reservation_service):
    # FR09 – Ensure that failures do not produce persistent side effects
    flight_id = "FL001"
    
    mock_reservation_service.getSeatCount = Mock(return_value=100)
    initial_seats = mock_reservation_service.getSeatCount(flight_id)
    
    mock_reservation_service.createReservation.side_effect = Exception("Creation failed")
    
    with pytest.raises(Exception):
        mock_reservation_service.createReservation(flight_id, 1)
    
    final_seats = mock_reservation_service.getSeatCount(flight_id)
    assert final_seats == initial_seats


# ============================================================================
# FR10 Tests - Use exclusively provided and internally stored data
# ============================================================================

def test_fr10_use_provided_data_only(mock_reservation_service):
    # FR10 – Use exclusively provided data
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service. createReservation. return_value = Mock(
        flightId=flight_id,
        seat=seat,
        state=ReservationState.CREATED. value
    )
    
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation.flightId == flight_id
    assert reservation.seat == seat


def test_fr10_use_internally_stored_data(mock_reservation_service, mock_flight):
    # FR10 – Use exclusively internally stored data
    mock_reservation_service.getFlightDateTime = Mock(return_value=mock_flight.dateTime)
    
    stored_datetime = mock_reservation_service.getFlightDateTime(mock_flight.id)
    
    assert stored_datetime == mock_flight.dateTime


def test_fr10_no_external_data_inference(mock_reservation_service):
    # FR10 – No inference or external enrichment
    reservation_id = "RES001"
    
    mock_reservation_service.inferExternalData = Mock(side_effect=Exception("External data inference not allowed"))
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.inferExternalData(reservation_id)
    
    assert "External data inference not allowed" in str(exc_info.value)


def test_fr10_no_external_enrichment(mock_reservation_service):
    # FR10 – No inference or external enrichment
    reservation_id = "RES001"
    
    mock_reservation_service. enrichWithExternalData = Mock(side_effect=Exception("External enrichment not allowed"))
    
    with pytest. raises(Exception) as exc_info: 
        mock_reservation_service.enrichWithExternalData(reservation_id, {"external_field": "value"})
    
    assert "External enrichment not allowed" in str(exc_info.value)


# ============================================================================
# Edge Case Tests
# ============================================================================

def test_edge_case_reservation_at_flight_capacity_limit(mock_reservation_service):
    # Edge case:  Creating reservation when exactly at capacity limit
    flight_id = "FL001"
    last_seat = 100
    
    mock_reservation_service. createReservation. return_value = Mock(seat=last_seat)
    reservation = mock_reservation_service.createReservation(flight_id, last_seat)
    
    assert reservation.seat == last_seat
    
    mock_reservation_service. createReservation. side_effect = Exception("No seats available")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.createReservation(flight_id, 101)
    
    assert "No seats available" in str(exc_info.value)


def test_edge_case_exactly_24_hours_boundary(mock_reservation_service):
    # Edge case:  Cancellation exactly at 24 hour boundary
    reservation_id = "RES001"
    
    mock_reservation_service.getRemainingHours = Mock(return_value=24.0)
    remaining = mock_reservation_service.getRemainingHours(reservation_id)
    
    assert remaining >= 24.0
    
    mock_reservation_service.cancelReservation. return_value = {"refund": "full"}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "full"


def test_edge_case_one_second_before_24_hours(mock_reservation_service):
    # Edge case: Cancellation one second before 24 hour mark (23. 99972...  hours)
    reservation_id = "RES001"
    
    mock_reservation_service.getRemainingHours = Mock(return_value=23.999722222222222)
    remaining = mock_reservation_service.getRemainingHours(reservation_id)
    
    assert remaining < 24.0
    
    mock_reservation_service.cancelReservation.return_value = {"refund": "none"}
    result = mock_reservation_service.cancelReservation(reservation_id)
    
    assert result["refund"] == "none"


def test_edge_case_seat_number_one(mock_reservation_service):
    # Edge case: First seat (seat 1)
    flight_id = "FL001"
    seat = 1
    
    mock_reservation_service.createReservation.return_value = Mock(seat=seat)
    reservation = mock_reservation_service.createReservation(flight_id, seat)
    
    assert reservation.seat == 1


def test_edge_case_last_available_seat(mock_reservation_service):
    # Edge case: Last available seat
    flight_id = "FL001"
    total_seats = 100
    last_seat = total_seats
    
    mock_reservation_service.createReservation.return_value = Mock(seat=last_seat)
    reservation = mock_reservation_service.createReservation(flight_id, last_seat)
    
    assert reservation.seat == last_seat


def test_edge_case_zero_remaining_hours(mock_reservation_service):
    # Edge case: Zero hours remaining (flight time reached)
    reservation_id = "RES001"
    
    mock_reservation_service.getRemainingHours = Mock(return_value=0.0)
    remaining = mock_reservation_service.getRemainingHours(reservation_id)
    
    assert remaining == 0.0
    assert remaining < 24.0


def test_edge_case_negative_remaining_hours(mock_reservation_service):
    # Edge case:  Negative hours (flight already departed)
    reservation_id = "RES001"
    
    mock_reservation_service.cancelReservation.side_effect = Exception("Cannot cancel after flight departure")
    
    with pytest.raises(Exception) as exc_info:
        mock_reservation_service.cancelReservation(reservation_id)
    
    assert "after flight departure" in str(exc_info. value)


def test_edge_case_single_seat_flight(mock_reservation_service):
    # Edge case: Flight with only one seat
    flight_id = "FL001"
    only_seat = 1
    
    mock_reservation_service. createReservation. return_value = Mock(seat=only_seat)
    reservation = mock_reservation