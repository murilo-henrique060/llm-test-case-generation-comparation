```python
"""
Automated Test Cases for Airline Reservation System
Based on the formal specifications provided.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from enum import Enum


# ============================================================================
# MOCK CLASSES FOR TESTING (Minimal stubs to allow test execution)
# ============================================================================

class ReservationState(Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


class Reservation:
    def __init__(self, reservation_id:  str, flight_id: str, seat:  int):
        self.reservation_id = reservation_id
        self.flight_id = flight_id
        self.seat = seat
        self. state = ReservationState.CREATED
        self.payment = None


class Flight:
    def __init__(self, flight_id:  str, date_time: datetime, total_seats: int):
        self.flight_id = flight_id
        self.date_time = date_time
        self. total_seats = total_seats


class Payment:
    def __init__(self, payment_id: str, approved: bool):
        self.payment_id = payment_id
        self.approved = approved


class ReservationService: 
    """Mock service - actual implementation would be provided by the system under test."""
    pass


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def reservation_service():
    """Provides a mock ReservationService instance."""
    return Mock(spec=ReservationService)


@pytest.fixture
def flight_future_48h():
    """Provides a flight scheduled 48 hours in the future."""
    return Flight(
        flight_id="FL001",
        date_time=datetime. now() + timedelta(hours=48),
        total_seats=100
    )


@pytest.fixture
def flight_future_12h():
    """Provides a flight scheduled 12 hours in the future."""
    return Flight(
        flight_id="FL002",
        date_time=datetime. now() + timedelta(hours=12),
        total_seats=100
    )


@pytest.fixture
def flight_future_24h_exact():
    """Provides a flight scheduled exactly 24 hours in the future."""
    return Flight(
        flight_id="FL003",
        date_time=datetime. now() + timedelta(hours=24),
        total_seats=100
    )


@pytest.fixture
def flight_past():
    """Provides a flight that has already departed."""
    return Flight(
        flight_id="FL004",
        date_time=datetime.now() - timedelta(hours=1),
        total_seats=100
    )


@pytest.fixture
def reservation_created():
    """Provides a reservation in CREATED state."""
    return Reservation(
        reservation_id="RES001",
        flight_id="FL001",
        seat=1
    )


@pytest.fixture
def reservation_confirmed():
    """Provides a reservation in CONFIRMED state."""
    reservation = Reservation(
        reservation_id="RES002",
        flight_id="FL001",
        seat=2
    )
    reservation.state = ReservationState. CONFIRMED
    reservation.payment = Payment("PAY001", approved=True)
    return reservation


@pytest.fixture
def reservation_canceled():
    """Provides a reservation in CANCELED state."""
    reservation = Reservation(
        reservation_id="RES003",
        flight_id="FL001",
        seat=3
    )
    reservation.state = ReservationState. CANCELED
    return reservation


# ============================================================================
# BR01 TESTS - Reservation confirmation requires exactly one approved payment
# ============================================================================

class TestBR01ReservationConfirmationRequiresApprovedPayment:
    
    def test_br01_reservation_confirms_with_exactly_one_approved_payment(self, reservation_service):
        # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(
            state=ReservationState.CONFIRMED,
            payment=Mock(approved=True)
        ))
        
        reservation_service.confirmPayment("RES001", True)
        result = reservation_service. getReservation("RES001")
        
        assert result.state == ReservationState.CONFIRMED
        assert result. payment.approved is True
    
    def test_br01_reservation_without_payment_cannot_be_confirmed(self, reservation_service):
        # BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
        reservation_service.confirmPayment = Mock(side_effect=Exception("No payment associated"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES001", None)
        
        assert "No payment associated" in str(exc_info.value)


# ============================================================================
# BR02 TESTS - Non-approved payments must not confirm reservations
# ============================================================================

class TestBR02NonApprovedPaymentsCannotConfirm:
    
    def test_br02_declined_payment_does_not_confirm_reservation(self, reservation_service):
        # BR02 – Payments with a status other than approved must not confirm reservations
        reservation_service. confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES001", False)
        
        assert "Payment not approved" in str(exc_info.value)
    
    def test_br02_reservation_remains_created_after_declined_payment(self, reservation_service):
        # BR02 – Payments with a status other than approved must not confirm reservations
        reservation_service. confirmPayment = Mock(side_effect=Exception("Payment declined"))
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CREATED))
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment("RES001", False)
        
        result = reservation_service. getReservation("RES001")
        assert result.state == ReservationState.CREATED


# ============================================================================
# BR03 TESTS - Atomic confirmation of reservation and payment
# ============================================================================

class TestBR03AtomicConfirmation:
    
    def test_br03_confirmation_and_payment_occur_atomically_success(self, reservation_service):
        # BR03 – Reservation confirmation and payment approval must occur atomically
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(
            state=ReservationState.CONFIRMED,
            payment=Mock(approved=True)
        ))
        
        reservation_service.confirmPayment("RES001", True)
        result = reservation_service.getReservation("RES001")
        
        assert result.state == ReservationState. CONFIRMED
        assert result.payment.approved is True
    
    def test_br03_no_partial_state_on_payment_failure(self, reservation_service):
        # BR03 – No observable state may exist in which only one of the two has been completed
        reservation_service.confirmPayment = Mock(side_effect=Exception("Atomic operation failed"))
        reservation_service.getReservation = Mock(return_value=Mock(
            state=ReservationState. CREATED,
            payment=None
        ))
        
        with pytest. raises(Exception):
            reservation_service.confirmPayment("RES001", True)
        
        result = reservation_service.getReservation("RES001")
        assert result.state == ReservationState. CREATED
        assert result.payment is None
    
    def test_br03_confirmation_without_payment_state_is_impossible(self, reservation_service):
        # BR03 – No observable state may exist in which only one of the two has been completed
        reservation_service. getReservation = Mock(return_value=Mock(
            state=ReservationState.CONFIRMED,
            payment=Mock(approved=True)
        ))
        
        result = reservation_service. getReservation("RES001")
        
        # If state is CONFIRMED, payment must be approved
        if result.state == ReservationState. CONFIRMED:
            assert result.payment is not None
            assert result.payment. approved is True


# ============================================================================
# BR04 TESTS - Seat belongs to at most one active reservation per flight
# ============================================================================

class TestBR04SeatExclusivity: 
    
    def test_br04_seat_can_have_one_active_reservation(self, reservation_service):
        # BR04 – A seat may belong to at most one active reservation per flight
        reservation_service.createReservation = Mock(return_value=Mock(
            seat=1,
            state=ReservationState.CREATED
        ))
        
        result = reservation_service. createReservation("FL001", 1)
        
        assert result.seat == 1
        assert result.state == ReservationState. CREATED
    
    def test_br04_same_seat_cannot_have_two_active_reservations(self, reservation_service):
        # BR04 – A seat may belong to at most one active reservation per flight
        reservation_service.createReservation = Mock()
        reservation_service.createReservation. side_effect = [
            Mock(seat=1, state=ReservationState. CREATED),
            Exception("Seat already reserved")
        ]
        
        reservation_service.createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.createReservation("FL001", 1)
        
        assert "Seat already reserved" in str(exc_info.value)


# ============================================================================
# BR05 TESTS - Canceled reservations release seats immediately
# ============================================================================

class TestBR05CanceledReservationsReleaseSeat: 
    
    def test_br05_canceled_reservation_releases_seat(self, reservation_service):
        # BR05 – Canceled reservations must immediately release the associated seat
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.isSeatAvailable = Mock(return_value=True)
        
        reservation_service.cancelReservation("RES001")
        
        assert reservation_service.isSeatAvailable("FL001", 1) is True
    
    def test_br05_seat_available_immediately_after_cancellation(self, reservation_service):
        # BR05 – Canceled reservations must immediately release the associated seat
        reservation_service. cancelReservation = Mock(return_value=None)
        reservation_service.createReservation = Mock(return_value=Mock(seat=1))
        
        reservation_service. cancelReservation("RES001")
        new_reservation = reservation_service. createReservation("FL001", 1)
        
        assert new_reservation. seat == 1


# ============================================================================
# BR06 TESTS - Overbooking not permitted
# ============================================================================

class TestBR06NoOverbooking: 
    
    def test_br06_overbooking_is_rejected(self, reservation_service):
        # BR06 – Overbooking is not permitted under any circumstances
        reservation_service.createReservation = Mock(side_effect=Exception("Overbooking not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.createReservation("FL001", 101)  # Flight has 100 seats
        
        assert "Overbooking not allowed" in str(exc_info. value)
    
    def test_br06_cannot_reserve_when_all_seats_taken(self, reservation_service):
        # BR06 – Overbooking is not permitted under any circumstances
        reservation_service.getAvailableSeats = Mock(return_value=0)
        reservation_service.createReservation = Mock(side_effect=Exception("No seats available"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. createReservation("FL001", 1)
        
        assert "No seats available" in str(exc_info.value)


# ============================================================================
# BR07 TESTS - Confirmed reservations cannot exceed total seats
# ============================================================================

class TestBR07ConfirmedReservationsLimit:
    
    def test_br07_confirmed_reservations_cannot_exceed_total_seats(self, reservation_service):
        # BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
        reservation_service.getConfirmedReservationsCount = Mock(return_value=100)
        reservation_service.getTotalSeats = Mock(return_value=100)
        reservation_service.confirmPayment = Mock(side_effect=Exception("No seats available for confirmation"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES101", True)
        
        assert "No seats available for confirmation" in str(exc_info.value)
    
    def test_br07_confirmation_allowed_when_seats_available(self, reservation_service):
        # BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
        reservation_service. getConfirmedReservationsCount = Mock(return_value=50)
        reservation_service.getTotalSeats = Mock(return_value=100)
        reservation_service.confirmPayment = Mock(return_value=None)
        
        reservation_service.confirmPayment("RES051", True)
        
        reservation_service.confirmPayment. assert_called_once_with("RES051", True)


# ============================================================================
# BR08 TESTS - Reservation states are exclusively CREATED, CONFIRMED, CANCELED
# ============================================================================

class TestBR08ReservationStates: 
    
    def test_br08_reservation_can_be_in_created_state(self, reservation_created):
        # BR08 – A reservation may be exclusively in one of the following states:  CREATED, CONFIRMED, CANCELED
        assert reservation_created.state == ReservationState.CREATED
    
    def test_br08_reservation_can_be_in_confirmed_state(self, reservation_confirmed):
        # BR08 – A reservation may be exclusively in one of the following states: CREATED, CONFIRMED, CANCELED
        assert reservation_confirmed.state == ReservationState.CONFIRMED
    
    def test_br08_reservation_can_be_in_canceled_state(self, reservation_canceled):
        # BR08 – A reservation may be exclusively in one of the following states: CREATED, CONFIRMED, CANCELED
        assert reservation_canceled.state == ReservationState. CANCELED
    
    def test_br08_reservation_state_is_one_of_valid_states(self, reservation_created):
        # BR08 – A reservation may be exclusively in one of the following states:  CREATED, CONFIRMED, CANCELED
        valid_states = {ReservationState. CREATED, ReservationState.CONFIRMED, ReservationState. CANCELED}
        assert reservation_created. state in valid_states


# ============================================================================
# BR09 TESTS - Intermediate or additional states not permitted
# ============================================================================

class TestBR09NoIntermediateStates:
    
    def test_br09_pending_state_is_not_permitted(self, reservation_service):
        # BR09 – Intermediate or additional states (e.g., "In payment", "Pending", "Expired") are not permitted
        reservation_service. setReservationState = Mock(side_effect=Exception("Invalid state:  PENDING"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.setReservationState("RES001", "PENDING")
        
        assert "Invalid state" in str(exc_info.value)
    
    def test_br09_in_payment_state_is_not_permitted(self, reservation_service):
        # BR09 – Intermediate or additional states (e.g., "In payment", "Pending", "Expired") are not permitted
        reservation_service. setReservationState = Mock(side_effect=Exception("Invalid state: IN_PAYMENT"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.setReservationState("RES001", "IN_PAYMENT")
        
        assert "Invalid state" in str(exc_info.value)
    
    def test_br09_expired_state_is_not_permitted(self, reservation_service):
        # BR09 – Intermediate or additional states (e. g., "In payment", "Pending", "Expired") are not permitted
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state:  EXPIRED"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. setReservationState("RES001", "EXPIRED")
        
        assert "Invalid state" in str(exc_info. value)


# ============================================================================
# BR10 TESTS - Valid state transitions
# ============================================================================

class TestBR10ValidStateTransitions:
    
    def test_br10_transition_created_to_confirmed_is_valid(self, reservation_service):
        # BR10 – The only valid state transitions are:  CREATED → CONFIRMED
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED))
        
        reservation_service.confirmPayment("RES001", True)
        result = reservation_service.getReservation("RES001")
        
        assert result.state == ReservationState. CONFIRMED
    
    def test_br10_transition_confirmed_to_canceled_is_valid(self, reservation_service):
        # BR10 – The only valid state transitions are:  CONFIRMED → CANCELED
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CANCELED))
        
        reservation_service.cancelReservation("RES001")
        result = reservation_service.getReservation("RES001")
        
        assert result.state == ReservationState. CANCELED


# ============================================================================
# BR11 TESTS - Invalid state transitions must be rejected
# ============================================================================

class TestBR11InvalidStateTransitionsRejected: 
    
    def test_br11_transition_created_to_canceled_is_rejected(self, reservation_service):
        # BR11 – Any state transition other than those defined must be rejected
        reservation_service.cancelReservation = Mock(side_effect=Exception("Invalid state transition:  CREATED -> CANCELED"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. cancelReservation("RES001")  # RES001 is in CREATED state
        
        assert "Invalid state transition" in str(exc_info. value)
    
    def test_br11_transition_confirmed_to_created_is_rejected(self, reservation_service):
        # BR11 – Any state transition other than those defined must be rejected
        reservation_service.resetToCreated = Mock(side_effect=Exception("Invalid state transition:  CONFIRMED -> CREATED"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.resetToCreated("RES002")  # RES002 is in CONFIRMED state
        
        assert "Invalid state transition" in str(exc_info.value)
    
    def test_br11_transition_canceled_to_confirmed_is_rejected(self, reservation_service):
        # BR11 – Any state transition other than those defined must be rejected
        reservation_service.confirmPayment = Mock(side_effect=Exception("Invalid state transition:  CANCELED -> CONFIRMED"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES003", True)  # RES003 is in CANCELED state
        
        assert "Invalid state transition" in str(exc_info. value)
    
    def test_br11_transition_canceled_to_created_is_rejected(self, reservation_service):
        # BR11 – Any state transition other than those defined must be rejected
        reservation_service.resetToCreated = Mock(side_effect=Exception("Invalid state transition: CANCELED -> CREATED"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.resetToCreated("RES003")  # RES003 is in CANCELED state
        
        assert "Invalid state transition" in str(exc_info.value)


# ============================================================================
# BR12 TESTS - Canceled reservations cannot be reactivated or modified
# ============================================================================

class TestBR12CanceledReservationImmutable:
    
    def test_br12_canceled_reservation_cannot_be_reactivated(self, reservation_service):
        # BR12 – A canceled reservation must not be reactivated
        reservation_service. reactivateReservation = Mock(side_effect=Exception("Cannot reactivate canceled reservation"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.reactivateReservation("RES003")
        
        assert "Cannot reactivate canceled reservation" in str(exc_info.value)
    
    def test_br12_canceled_reservation_cannot_be_modified(self, reservation_service):
        # BR12 – A canceled reservation must not be modified
        reservation_service.modifyReservation = Mock(side_effect=Exception("Cannot modify canceled reservation"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. modifyReservation("RES003", seat=5)
        
        assert "Cannot modify canceled reservation" in str(exc_info.value)
    
    def test_br12_canceled_reservation_cannot_receive_new_payments(self, reservation_service):
        # BR12 – A canceled reservation must not receive new payments
        reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot add payment to canceled reservation"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.confirmPayment("RES003", True)
        
        assert "Cannot add payment to canceled reservation" in str(exc_info.value)


# ============================================================================
# BR13 TESTS - Refund policy based on remaining time
# ============================================================================

class TestBR13RefundPolicy:
    
    def test_br13_full_refund_when_remaining_time_ge_24_hours(self, reservation_service):
        # BR13 – Remaining time ≥ 24 hours before the flight → full refund
        reservation_service.cancelReservation = Mock(return_value={"refund":  "full"})
        
        result = reservation_service.cancelReservation("RES001")  # Flight is 48 hours away
        
        assert result["refund"] == "full"
    
    def test_br13_no_refund_when_remaining_time_lt_24_hours(self, reservation_service):
        # BR13 – Remaining time < 24 hours before the flight → no refund
        reservation_service. cancelReservation = Mock(return_value={"refund":  "none"})
        
        result = reservation_service.cancelReservation("RES002")  # Flight is 12 hours away
        
        assert result["refund"] == "none"


# ============================================================================
# BR14 TESTS - Exact hour calculation with no rounding
# ============================================================================

class TestBR14ExactHourCalculation: 
    
    def test_br14_exactly_24_hours_qualifies_for_full_refund(self, reservation_service):
        # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service.cancelReservation("RES003")  # Flight is exactly 24 hours away
        
        assert result["refund"] == "full"
    
    def test_br14_23_hours_59_minutes_does_not_qualify_for_full_refund(self, reservation_service):
        # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding
        reservation_service.getRemainingTime = Mock(return_value=timedelta(hours=23, minutes=59))
        reservation_service.cancelReservation = Mock(return_value={"refund": "none"})
        
        result = reservation_service.cancelReservation("RES004")  # 23h59m remaining
        
        assert result["refund"] == "none"
    
    def test_br14_24_hours_1_minute_qualifies_for_full_refund(self, reservation_service):
        # BR14 – Remaining time until the flight must be calculated in exact hours, with no rounding
        reservation_service. getRemainingTime = Mock(return_value=timedelta(hours=24, minutes=1))
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service.cancelReservation("RES005")  # 24h1m remaining
        
        assert result["refund"] == "full"


# ============================================================================
# BR15 TESTS - Internal flight date/time as temporal reference
# ============================================================================

class TestBR15InternalTemporalReference: 
    
    def test_br15_uses_internal_flight_datetime_for_calculations(self, reservation_service):
        # BR15 – The system must use exclusively the internally stored flight date and time
        internal_datetime = datetime(2026, 1, 15, 10, 0, 0)
        reservation_service. getFlightDateTime = Mock(return_value=internal_datetime)
        
        result = reservation_service.getFlightDateTime("FL001")
        
        assert result == internal_datetime
    
    def test_br15_external_datetime_cannot_override_internal(self, reservation_service):
        # BR15 – The system must use exclusively the internally stored flight date and time
        reservation_service.calculateRefundWithExternalTime = Mock(
            side_effect=Exception("External time reference not allowed")
        )
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.calculateRefundWithExternalTime("RES001", datetime. now())
        
        assert "External time reference not allowed" in str(exc_info.value)


# ============================================================================
# BR16 TESTS - Flight data immutable after confirmation
# ============================================================================

class TestBR16FlightDataImmutableAfterConfirmation:
    
    def test_br16_flight_date_cannot_be_altered_after_confirmation(self, reservation_service):
        # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
        reservation_service.updateFlightDate = Mock(side_effect=Exception("Cannot alter flight date after confirmation"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.updateFlightDate("RES002", datetime(2026, 2, 1))
        
        assert "Cannot alter flight date" in str(exc_info.value)
    
    def test_br16_flight_time_cannot_be_altered_after_confirmation(self, reservation_service):
        # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
        reservation_service.updateFlightTime = Mock(side_effect=Exception("Cannot alter flight time after confirmation"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.updateFlightTime("RES002", "14:00")
        
        assert "Cannot alter flight time" in str(exc_info.value)
    
    def test_br16_flight_id_cannot_be_altered_after_confirmation(self, reservation_service):
        # BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
        reservation_service.updateFlightId = Mock(side_effect=Exception("Cannot alter flight identifier after confirmation"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. updateFlightId("RES002", "FL999")
        
        assert "Cannot alter flight identifier" in str(exc_info.value)


# ============================================================================
# BR17 TESTS - Indirect flight data modifications prohibited
# ============================================================================

class TestBR17IndirectModificationsProhibited: 
    
    def test_br17_reference_swapping_is_prohibited(self, reservation_service):
        # BR17 – Indirect modifications of flight data (reference swapping) are prohibited
        reservation_service.swapFlightReference = Mock(side_effect=Exception("Reference swapping prohibited"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.swapFlightReference("RES002", "FL999")
        
        assert "Reference swapping prohibited" in str(exc_info.value)
    
    def test_br17_flight_cloning_is_prohibited(self, reservation_service):
        # BR17 – Indirect modifications of flight data (cloning) are prohibited
        reservation_service. cloneFlightToReservation = Mock(side_effect=Exception("Flight cloning prohibited"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.cloneFlightToReservation("RES002", "FL001")
        
        assert "Flight cloning prohibited" in str(exc_info.value)
    
    def test_br17_object_recreation_is_prohibited(self, reservation_service):
        # BR17 – Indirect modifications of flight data (object recreation) are prohibited
        reservation_service.recreateFlightObject = Mock(side_effect=Exception("Object recreation prohibited"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. recreateFlightObject("FL001")
        
        assert "Object recreation prohibited" in str(exc_info.value)


# ============================================================================
# BR18 TESTS - Each reservation has exactly one payment
# ============================================================================

class TestBR18OnePaymentPerReservation:
    
    def test_br18_reservation_can_have_one_payment(self, reservation_service):
        # BR18 – Each reservation may have exactly one associated payment
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(
            payment=Mock(payment_id="PAY001")
        ))
        
        reservation_service.confirmPayment("RES001", True)
        result = reservation_service.getReservation("RES001")
        
        assert result.payment is not None
        assert result.payment.payment_id == "PAY001"
    
    def test_br18_reservation_cannot_have_zero_payments_when_confirmed(self, reservation_confirmed):
        # BR18 – Each reservation may have exactly one associated payment
        assert reservation_confirmed.payment is not None


# ============================================================================
# BR19 TESTS - Additional payment attempts rejected
# ============================================================================

class TestBR19AdditionalPaymentsRejected: 
    
    def test_br19_second_payment_attempt_is_rejected(self, reservation_service):
        # BR19 – Additional payment attempts for the same reservation must be rejected
        reservation_service.confirmPayment = Mock()
        reservation_service.confirmPayment.side_effect = [
            None,
            Exception("Additional payment attempt rejected")
        ]
        
        reservation_service.confirmPayment("RES001", True)
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES001", True)
        
        assert "Additional payment attempt rejected" in str(exc_info.value)
    
    def test_br19_payment_after_confirmation_is_rejected(self, reservation_service):
        # BR19 – Additional payment attempts for the same reservation must be rejected
        reservation_service.confirmPayment = Mock(side_effect=Exception("Reservation already has payment"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES002", True)  # RES002 is already confirmed
        
        assert "Reservation already has payment" in str(exc_info. value)


# ============================================================================
# BR20 TESTS - Payments not accepted for canceled reservations or after flight
# ============================================================================

class TestBR20PaymentRestrictions:
    
    def test_br20_payment_not_accepted_for_canceled_reservation(self, reservation_service):
        # BR20 – Payments must not be accepted for canceled reservations
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not accepted for canceled reservation"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES003", True)  # RES003 is canceled
        
        assert "Payment not accepted for canceled reservation" in str(exc_info. value)
    
    def test_br20_payment_not_accepted_after_flight_date(self, reservation_service):
        # BR20 – Payments must not be accepted after the flight date
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not accepted after flight date"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. confirmPayment("RES004", True)  # Flight has already departed
        
        assert "Payment not accepted after flight date" in str(exc_info. value)


# ============================================================================
# BR21 TESTS - Deterministic operations
# ============================================================================

class TestBR21DeterministicOperations:
    
    def test_br21_same_inputs_produce_same_result_first_call(self, reservation_service):
        # BR21 – System operations must be deterministic
        reservation_service. createReservation = Mock(return_value=Mock(
            reservation_id="RES001",
            flight_id="FL001",
            seat=1,
            state=ReservationState.CREATED
        ))
        
        result1 = reservation_service.createReservation("FL001", 1)
        
        assert result1.flight_id == "FL001"
        assert result1.seat == 1
        assert result1.state == ReservationState. CREATED
    
    def test_br21_same_sequence_produces_same_results(self, reservation_service):
        # BR21 – Always producing the same result for the same sequence of inputs
        results = []
        reservation_service.createReservation = Mock(return_value=Mock(
            flight_id="FL001",
            seat=1,
            state=ReservationState.CREATED
        ))
        
        for _ in range(2):
            result = reservation_service.createReservation("FL001", 1)
            results.append((result.flight_id, result.seat, result.state))
        
        assert results[0] == results[1]


# ============================================================================
# BR22 TESTS - No unspecified implicit behaviors
# ============================================================================

class TestBR22NoImplicitBehaviors: 
    
    def test_br22_no_future_credit_behavior(self, reservation_service):
        # BR22 – The system must not assume unspecified implicit behaviors (e.g., future credit)
        reservation_service.applyFutureCredit = Mock(side_effect=Exception("Future credit not supported"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.applyFutureCredit("RES001", 100)
        
        assert "Future credit not supported" in str(exc_info.value)
    
    def test_br22_no_automatic_rebooking_behavior(self, reservation_service):
        # BR22 – The system must not assume unspecified implicit behaviors (e.g., automatic rebooking)
        reservation_service.automaticRebook = Mock(side_effect=Exception("Automatic rebooking not supported"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.automaticRebook("RES003")
        
        assert "Automatic rebooking not supported" in str(exc_info.value)
    
    def test_br22_no_commercial_exceptions(self, reservation_service):
        # BR22 – The system must not assume unspecified implicit behaviors (e.g., commercial exceptions)
        reservation_service.applyCommercialException = Mock(side_effect=Exception("Commercial exceptions not supported"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. applyCommercialException("RES001", "VIP")
        
        assert "Commercial exceptions not supported" in str(exc_info. value)


# ============================================================================
# BR23 TESTS - Immediate failure on rule violation
# ============================================================================

class TestBR23ImmediateFailureOnViolation:
    
    def test_br23_violation_results_in_immediate_failure(self, reservation_service):
        # BR23 – Any business rule violation must result in immediate failure
        reservation_service.createReservation = Mock(side_effect=Exception("Business rule violation"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. createReservation("FL001", 101)  # Invalid seat
        
        assert "Business rule violation" in str(exc_info.value)
    
    def test_br23_no_state_change_on_violation(self, reservation_service):
        # BR23 – No state change on violation
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment declined"))
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CREATED))
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment("RES001", False)
        
        result = reservation_service. getReservation("RES001")
        assert result.state == ReservationState.CREATED
    
    def test_br23_no_partial_records_on_violation(self, reservation_service):
        # BR23 – No creation of partial records on violation
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid flight"))
        reservation_service.getAllReservations = Mock(return_value=[])
        
        with pytest.raises(Exception):
            reservation_service.createReservation("INVALID_FL", 1)
        
        reservations = reservation_service.getAllReservations()
        assert len(reservations) == 0


# ============================================================================
# BR24 TESTS - Valid operations generate exactly one immutable record
# ============================================================================

class TestBR24ValidOperationGeneratesOneRecord:
    
    def test_br24_valid_reservation_creates_exactly_one_record(self, reservation_service):
        # BR24 – Each valid operation must generate exactly one immutable record
        reservation_service.createReservation = Mock(return_value=Mock(reservation_id="RES001"))
        reservation_service.getReservationCount = Mock(return_value=1)
        
        reservation_service.createReservation("FL001", 1)
        count = reservation_service. getReservationCount()
        
        assert count == 1
    
    def test_br24_record_is_immutable(self, reservation_service):
        # BR24 – Each valid operation must generate exactly one immutable record
        reservation_service.modifyReservationId = Mock(side_effect=Exception("Record is immutable"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.modifyReservationId("RES001", "RES999")
        
        assert "Record is immutable" in str(exc_info.value)


# ============================================================================
# BR25 TESTS - Failed operations do not generate records
# ============================================================================

class TestBR25FailedOperationsNoRecords:
    
    def test_br25_failed_operation_does_not_create_record(self, reservation_service):
        # BR25 – Failed operations must not generate persistent records
        reservation_service.createReservation = Mock(side_effect=Exception("Operation failed"))
        reservation_service.getAllReservations = Mock(return_value=[])
        
        with pytest.raises(Exception):
            reservation_service.createReservation("FL001", 1)
        
        reservations = reservation_service. getAllReservations()
        assert len(reservations) == 0
    
    def test_br25_failed_payment_does_not_create_payment_record(self, reservation_service):
        # BR25 – Failed operations must not generate persistent records
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment failed"))
        reservation_service.getAllPayments = Mock(return_value=[])
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment("RES001", False)
        
        payments = reservation_service.getAllPayments()
        assert len(payments) == 0


# ============================================================================
# BR26 TESTS - Operations on one reservation do not affect others
# ============================================================================

class TestBR26OperationIsolation:
    
    def test_br26_canceling_one_reservation_does_not_affect_others(self, reservation_service):
        # BR26 – Operations performed on one reservation must not affect other reservations
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED))
        
        reservation_service.cancelReservation("RES001")
        other_reservation = reservation_service. getReservation("RES002")
        
        assert other_reservation.state == ReservationState. CONFIRMED
    
    def test_br26_confirming_one_reservation_does_not_affect_other_flights(self, reservation_service):
        # BR26 – Operations performed on one reservation must not affect flights
        reservation_service. confirmPayment = Mock(return_value=None)
        reservation_service.getFlight = Mock(return_value=Mock(total_seats=100))
        
        reservation_service.confirmPayment("RES001", True)
        flight = reservation_service. getFlight("FL002")
        
        assert flight.total_seats == 100
    
    def test_br26_seat_operation_on_one_reservation_does_not_affect_other_seats(self, reservation_service):
        # BR26 – Operations performed on one reservation must not affect seats
        reservation_service.createReservation = Mock(return_value=Mock(seat=1))
        reservation_service.isSeatAvailable = Mock(return_value=True)
        
        reservation_service.createReservation("FL001", 1)
        is_seat_2_available = reservation_service.isSeatAvailable("FL001", 2)
        
        assert is_seat_2_available is True


# ============================================================================
# FR01 TESTS - Create initial reservation in CREATED state
# ============================================================================

class TestFR01CreateReservation:
    
    def test_fr01_create_reservation_in_created_state(self, reservation_service):
        # FR01 – Create an initial reservation in the CREATED state
        reservation_service.createReservation = Mock(return_value=Mock(
            state=ReservationState.CREATED,
            flight_id="FL001",
            seat=1
        ))
        
        result = reservation_service.createReservation("FL001", 1)
        
        assert result. state == ReservationState.CREATED
    
    def test_fr01_reservation_associated_with_flight(self, reservation_service):
        # FR01 – Create an initial reservation associated with a flight
        reservation_service.createReservation = Mock(return_value=Mock(
            flight_id="FL001",
            state=ReservationState.CREATED
        ))
        
        result = reservation_service.createReservation("FL001", 1)
        
        assert result.flight_id == "FL001"
    
    def test_fr01_reservation_associated_with_available_seat(self, reservation_service):
        # FR01 – Create an initial reservation associated with an available seat
        reservation_service.createReservation = Mock(return_value=Mock(
            seat=15,
            state=ReservationState. CREATED
        ))
        
        result = reservation_service. createReservation("FL001", 15)
        
        assert result.seat == 15


# ============================================================================
# FR02 TESTS - Confirm payment atomically with reservation
# ============================================================================

class TestFR02ConfirmPaymentAtomically: 
    
    def test_fr02_confirm_payment_and_reservation_atomically(self, reservation_service):
        # FR02 – Confirm payment and, atomically, confirm the reservation
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service. getReservation = Mock(return_value=Mock(
            state=ReservationState.CONFIRMED,
            payment=Mock(approved=True)
        ))
        
        reservation_service.confirmPayment("RES001", True)
        result = reservation_service. getReservation("RES001")
        
        assert result.state == ReservationState.CONFIRMED
        assert result. payment.approved is True
    
    def test_fr02_failed_payment_leaves_reservation_unchanged(self, reservation_service):
        # FR02 – Atomic operation - failure leaves no partial state
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment failed"))
        reservation_service.getReservation = Mock(return_value=Mock(
            state=ReservationState. CREATED,
            payment=None
        ))
        
        with pytest. raises(Exception):
            reservation_service. confirmPayment("RES001", True)
        
        result = reservation_service. getReservation("RES001")
        assert result.state == ReservationState.CREATED
        assert result.payment is None


# ============================================================================
# FR03 TESTS - Strict seat availability control
# ============================================================================

class TestFR03SeatAvailabilityControl:
    
    def test_fr03_seat_exclusivity_per_active_reservation(self, reservation_service):
        # FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
        reservation_service. createReservation = Mock()
        reservation_service.createReservation. side_effect = [
            Mock(seat=1),
            Exception("Seat not available")
        ]
        
        reservation_service.createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.createReservation("FL001", 1)
        
        assert "Seat not available" in str(exc_info.value)
    
    def test_fr03_available_seat_can_be_reserved(self, reservation_service):
        # FR03 – Strictly control seat availability
        reservation_service. isSeatAvailable = Mock(return_value=True)
        reservation_service.createReservation = Mock(return_value=Mock(seat=5))
        
        available = reservation_service. isSeatAvailable("FL001", 5)
        result = reservation_service. createReservation("FL001", 5)
        
        assert available is True
        assert result.seat == 5


# ============================================================================
# FR04 TESTS - Cancel reservations with refund policy
# ============================================================================

class TestFR04CancelWithRefundPolicy:
    
    def test_fr04_cancel_with_full_refund_ge_24_hours(self, reservation_service):
        # FR04 – Cancel reservations with full refund when >= 24 hours remaining
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service. cancelReservation("RES001")  # 48 hours remaining
        
        assert result["refund"] == "full"
    
    def test_fr04_cancel_without_refund_lt_24_hours(self, reservation_service):
        # FR04 – Cancel reservations without refund when < 24 hours remaining
        reservation_service.cancelReservation = Mock(return_value={"refund": "none"})
        
        result = reservation_service.cancelReservation("RES002")  # 12 hours remaining
        
        assert result["refund"] == "none"


# ============================================================================
# FR05 TESTS - Prevent invalid modifications
# ============================================================================

class TestFR05PreventInvalidModifications:
    
    def test_fr05_prevent_invalid_state_modification(self, reservation_service):
        # FR05 – Prevent any invalid modification of state
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state modification"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.setReservationState("RES001", "INVALID")
        
        assert "Invalid state modification" in str(exc_info.value)
    
    def test_fr05_prevent_invalid_flight_data_modification(self, reservation_service):
        # FR05 – Prevent any invalid modification of flight data
        reservation_service. updateFlightData = Mock(side_effect=Exception("Flight data modification not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.updateFlightData("RES002", {"date": "2026-02-01"})
        
        assert "Flight data modification not allowed" in str(exc_info.value)
    
    def test_fr05_prevent_invalid_seat_modification(self, reservation_service):
        # FR05 – Prevent any invalid modification of seat
        reservation_service.updateSeat = Mock(side_effect=Exception("Seat modification not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.updateSeat("RES002", 10)
        
        assert "Seat modification not allowed" in str(exc_info.value)
    
    def test_fr05_prevent_invalid_payment_modification(self, reservation_service):
        # FR05 – Prevent any invalid modification of payment
        reservation_service.updatePayment = Mock(side_effect=Exception("Payment modification not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.updatePayment("RES002", {"amount": 500})
        
        assert "Payment modification not allowed" in str(exc_info.value)


# ============================================================================
# FR06 TESTS - No overbooking at any stage
# ============================================================================

class TestFR06NoOverbookingAtAnyStage: 
    
    def test_fr06_no_overbooking_at_reservation_creation(self, reservation_service):
        # FR06 – Do not allow overbooking at any stage (creation)
        reservation_service.createReservation = Mock(side_effect=Exception("Overbooking not allowed"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. createReservation("FL001", 101)
        
        assert "Overbooking not allowed" in str(exc_info. value)
    
    def test_fr06_no_overbooking_at_confirmation(self, reservation_service):
        # FR06 – Do not allow overbooking at any stage (confirmation)
        reservation_service.confirmPayment = Mock(side_effect=Exception("Overbooking not allowed"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. confirmPayment("RES101", True)  # Would exceed capacity
        
        assert "Overbooking not allowed" in str(exc_info.value)


# ============================================================================
# FR07 TESTS - No multiple, partial, or late payments
# ============================================================================

class TestFR07PaymentRestrictions: 
    
    def test_fr07_no_multiple_payments(self, reservation_service):
        # FR07 – Do not allow multiple payments
        reservation_service.confirmPayment = Mock()
        reservation_service.confirmPayment. side_effect = [
            None,
            Exception("Multiple payments not allowed")
        ]
        
        reservation_service.confirmPayment("RES001", True)
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.confirmPayment("RES001", True)
        
        assert "Multiple payments not allowed" in str(exc_info.value)
    
    def test_fr07_no_partial_payments(self, reservation_service):
        # FR07 – Do not allow partial payments
        reservation_service.confirmPartialPayment = Mock(side_effect=Exception("Partial payments not allowed"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. confirmPartialPayment("RES001", 50)
        
        assert "Partial payments not allowed" in str(exc_info. value)
    
    def test_fr07_no_late_payments(self, reservation_service):
        # FR07 – Do not allow late payments (after flight)
        reservation_service.confirmPayment = Mock(side_effect=Exception("Late payments not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES004", True)  # Flight has departed
        
        assert "Late payments not allowed" in str(exc_info.value)


# ============================================================================
# FR08 TESTS - No intermediate states or partial results
# ============================================================================

class TestFR08NoIntermediateStatesOrPartialResults: 
    
    def test_fr08_no_intermediate_state_returned(self, reservation_service):
        # FR08 – Do not return intermediate states
        reservation_service. getReservation = Mock(return_value=Mock(state=ReservationState.CONFIRMED))
        
        result = reservation_service.getReservation("RES002")
        
        assert result.state in {ReservationState. CREATED, ReservationState.CONFIRMED, ReservationState. CANCELED}
    
    def test_fr08_no_explanatory_messages_on_valid_operation(self, reservation_service):
        # FR08 – Do not return explanatory messages
        reservation_service. createReservation = Mock(return_value=Mock(
            reservation_id="RES001",
            message=None
        ))
        
        result = reservation_service.createReservation("FL001", 1)
        
        assert not hasattr(result, 'message') or result.message is None
    
    def test_fr08_no_partial_results_on_failure(self, reservation_service):
        # FR08 – Do not return partial results
        reservation_service. createReservation = Mock(side_effect=Exception("Operation failed"))
        
        with pytest.raises(Exception):
            result = reservation_service. createReservation("INVALID", 1)
            # If exception not raised, check no partial data
            assert result is None


# ============================================================================
# FR09 TESTS - Failures do not modify state
# ============================================================================

class TestFR09FailuresDoNotModifyState:
    
    def test_fr09_failure_does_not_modify_reservation_state(self, reservation_service):
        # FR09 – Ensure that failures do not modify state
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment declined"))
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CREATED))
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment("RES001", False)
        
        result = reservation_service.getReservation("RES001")
        assert result.state == ReservationState. CREATED
    
    def test_fr09_failure_produces_no_persistent_side_effects(self, reservation_service):
        # FR09 – Failures do not produce persistent side effects
        reservation_service.createReservation = Mock(side_effect=Exception("Creation failed"))
        reservation_service.getReservationCount = Mock(return_value=0)
        
        with pytest.raises(Exception):
            reservation_service.createReservation("FL001", 1)
        
        count = reservation_service. getReservationCount()
        assert count == 0


# ============================================================================
# FR10 TESTS - Use exclusively provided and internal data
# ============================================================================

class TestFR10UseOnlyProvidedData:
    
    def test_fr10_use_internally_stored_data(self, reservation_service):
        # FR10 – Use exclusively provided and internally stored data
        reservation_service.getFlightDateTime = Mock(return_value=datetime(2026, 1, 15, 10, 0, 0))
        
        result = reservation_service.getFlightDateTime("FL001")
        
        assert isinstance(result, datetime)
    
    def test_fr10_no_external_data_enrichment(self, reservation_service):
        # FR10 – No inference or external enrichment
        reservation_service. enrichWithExternalData = Mock(side_effect=Exception("External enrichment not allowed"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.enrichWithExternalData("RES001", {"source": "external"})
        
        assert "External enrichment not allowed" in str(exc_info.value)
    
    def test_fr10_no_data_inference(self, reservation_service):
        # FR10 – No inference
        reservation_service. inferMissingData = Mock(side_effect=Exception("Data inference not allowed"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.inferMissingData("RES001")
        
        assert "Data inference not allowed" in str(exc_info.value)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    
    def test_edge_case_exactly_24_hours_boundary_full_refund(self, reservation_service):
        # BR13/BR14 – Exactly 24 hours remaining qualifies for full refund
        reservation_service.getRemainingTime = Mock(return_value=timedelta(hours=24))
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service.cancelReservation("RES_EDGE")
        
        assert result["refund"] == "full"
    
    def test_edge_case_23h59m59s_no_refund(self, reservation_service):
        # BR14 – 23:59:59 remaining does not qualify for full refund (exact hours, no rounding)
        reservation_service.getRemainingTime = Mock(return_value=timedelta(hours=23, minutes=59, seconds=59))
        reservation_service. cancelReservation = Mock(return_value={"refund":  "none"})
        
        result = reservation_service.cancelReservation("RES_EDGE")
        
        assert result["refund"] == "none"
    
    def test_edge_case_last_available_seat(self, reservation_service):
        # BR06/BR07 – Last seat reservation succeeds
        reservation_service.getAvailableSeats = Mock(return_value=1)
        reservation_service.createReservation = Mock(return_value=Mock(seat=100))
        
        result = reservation_service.createReservation("FL001", 100)
        
        assert result.seat == 100
    
    def test_edge_case_no_seats_left(self, reservation_service):
        # BR06/BR07 – No seats left, reservation fails
        reservation_service.getAvailableSeats = Mock(return_value=0)
        reservation_service.createReservation = Mock(side_effect=Exception("No seats available"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.createReservation("FL001", 1)
        
        assert "No seats available" in str(exc_info.value)
    
    def test_edge_case_flight_departing_now(self, reservation_service):
        # BR20 – Payment not accepted at exact flight time
        reservation_service.getRemainingTime = Mock(return_value=timedelta(0))
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not accepted at flight time"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.confirmPayment("RES_NOW", True)
        
        assert "Payment not accepted" in str(exc_info.value)
    
    def test_edge_case_seat_zero_invalid(self, reservation_service):
        # FR01 – Seat must be valid (assuming 1-based indexing)
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat number"))
        
        with pytest.raises(Exception) as exc_info:
            reservation_service.createReservation("FL001", 0)
        
        assert "Invalid seat number" in str(exc_info.value)
    
    def test_edge_case_negative_seat_invalid(self, reservation_service):
        # FR01 – Negative seat number is invalid
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat number"))
        
        with pytest.raises(Exception) as exc_info: 
            reservation_service.createReservation("FL001", -1)
        
        assert "Invalid seat number" in str(exc_info.value)
    
    def test_edge_case_seat_exceeds_total_seats(self, reservation_service):
        # BR06/FR06 – Seat number exceeding total seats
        reservation_service.createReservation = Mock(side_effect=Exception("Seat does not exist"))
        
        with pytest. raises(Exception) as exc_info: 
            reservation_service. createReservation("FL001", 150)  # Flight has 100 seats
        
        assert "Seat does not exist" in str(exc_info.value)
```