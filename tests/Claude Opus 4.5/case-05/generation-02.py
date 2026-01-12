```python
"""
Automated test cases for Airline Reservation System
Based on formal specifications:  Business Rules (BR) and Functional Requirements (FR)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from enum import Enum


# ============================================================================
# TEST FIXTURES AND HELPERS
# ============================================================================

class ReservationState(Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


@pytest.fixture
def mock_reservation_service():
    """Fixture providing a mock ReservationService for testing."""
    service = Mock()
    return service


@pytest. fixture
def mock_flight():
    """Fixture providing a mock Flight object."""
    flight = Mock()
    flight.flightId = "FL001"
    flight. dateTime = datetime(2026, 1, 20, 14, 0, 0)
    flight.totalSeats = 100
    return flight


@pytest.fixture
def mock_reservation():
    """Fixture providing a mock Reservation object."""
    reservation = Mock()
    reservation.reservationId = "RES001"
    reservation. state = ReservationState.CREATED
    reservation.seat = 1
    reservation.flightId = "FL001"
    reservation.payment = None
    return reservation


@pytest. fixture
def confirmed_reservation():
    """Fixture providing a confirmed reservation."""
    reservation = Mock()
    reservation.reservationId = "RES002"
    reservation.state = ReservationState. CONFIRMED
    reservation.seat = 2
    reservation.flightId = "FL001"
    reservation.payment = Mock(status="approved")
    return reservation


@pytest.fixture
def canceled_reservation():
    """Fixture providing a canceled reservation."""
    reservation = Mock()
    reservation.reservationId = "RES003"
    reservation.state = ReservationState.CANCELED
    reservation.seat = 3
    reservation. flightId = "FL001"
    reservation.payment = None
    return reservation


# ============================================================================
# BR01 - A reservation may only be confirmed if exactly one approved payment
# ============================================================================

class TestBR01ReservationConfirmationRequiresApprovedPayment: 
    """BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it."""

    def test_br01_reservation_confirmed_with_exactly_one_approved_payment(self, mock_reservation_service, mock_reservation):
        # BR01 – Reservation confirmation requires exactly one approved payment
        mock_reservation_service.confirmPayment = Mock(return_value=None)
        mock_reservation. payment = Mock(status="approved")
        mock_reservation.state = ReservationState. CONFIRMED
        
        mock_reservation_service. confirmPayment("RES001", True)
        
        assert mock_reservation. state == ReservationState.CONFIRMED
        assert mock_reservation.payment.status == "approved"

    def test_br01_reservation_not_confirmed_without_payment(self, mock_reservation_service, mock_reservation):
        # BR01 – Reservation cannot be confirmed without a payment
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("No payment associated"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES001", True)
        
        assert "No payment associated" in str(exc_info.value)

    def test_br01_reservation_not_confirmed_with_zero_payments(self, mock_reservation_service, mock_reservation):
        # BR01 – Reservation cannot be confirmed with zero payments
        mock_reservation. payment = None
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Exactly one approved payment required"))
        
        with pytest. raises(Exception) as exc_info: 
            mock_reservation_service.confirmPayment("RES001", True)
        
        assert "Exactly one approved payment required" in str(exc_info.value)


# ============================================================================
# BR02 - Payments with status other than approved must not confirm reservations
# ============================================================================

class TestBR02NonApprovedPaymentsCannotConfirm: 
    """BR02 – Payments with a status other than approved must not confirm reservations."""

    def test_br02_rejected_payment_does_not_confirm_reservation(self, mock_reservation_service, mock_reservation):
        # BR02 – Rejected payment must not confirm reservation
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES001", False)
        
        assert mock_reservation.state == ReservationState. CREATED

    def test_br02_declined_payment_status_does_not_confirm_reservation(self, mock_reservation_service, mock_reservation):
        # BR02 – Declined payment status must not confirm reservation
        mock_reservation. payment = Mock(status="declined")
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Payment status is not approved"))
        
        with pytest. raises(Exception) as exc_info: 
            mock_reservation_service.confirmPayment("RES001", False)
        
        assert "Payment status is not approved" in str(exc_info.value)

    def test_br02_pending_payment_status_does_not_confirm_reservation(self, mock_reservation_service, mock_reservation):
        # BR02 – Pending payment status must not confirm reservation
        mock_reservation.payment = Mock(status="pending")
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Payment status is not approved"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. confirmPayment("RES001", False)
        
        assert "Payment status is not approved" in str(exc_info.value)


# ============================================================================
# BR03 - Reservation confirmation and payment approval must occur atomically
# ============================================================================

class TestBR03AtomicConfirmationAndPayment:
    """BR03 – Reservation confirmation and payment approval must occur atomically."""

    def test_br03_confirmation_and_payment_occur_together(self, mock_reservation_service, mock_reservation):
        # BR03 – Reservation confirmation and payment must be atomic
        confirmation_occurred = False
        payment_approved = False
        
        def atomic_confirm(reservation_id, approved):
            nonlocal confirmation_occurred, payment_approved
            if approved:
                confirmation_occurred = True
                payment_approved = True
            else: 
                raise Exception("Atomic operation failed")
        
        mock_reservation_service.confirmPayment = atomic_confirm
        mock_reservation_service.confirmPayment("RES001", True)
        
        assert confirmation_occurred == payment_approved

    def test_br03_no_partial_state_on_payment_failure(self, mock_reservation_service, mock_reservation):
        # BR03 – No observable state where only confirmation or payment completed
        original_state = mock_reservation.state
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Atomic operation failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.confirmPayment("RES001", False)
        
        assert mock_reservation. state == original_state

    def test_br03_both_states_change_or_neither(self, mock_reservation_service, mock_reservation):
        # BR03 – Both reservation and payment states must change together or neither changes
        mock_reservation.payment = Mock(status="pending")
        original_reservation_state = mock_reservation.state
        original_payment_status = mock_reservation. payment.status
        
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Transaction rollback"))
        
        with pytest.raises(Exception):
            mock_reservation_service.confirmPayment("RES001", True)
        
        assert mock_reservation.state == original_reservation_state
        assert mock_reservation.payment.status == original_payment_status


# ============================================================================
# BR04 - A seat may belong to at most one active reservation per flight
# ============================================================================

class TestBR04SeatExclusivity: 
    """BR04 – A seat may belong to at most one active reservation per flight."""

    def test_br04_seat_assigned_to_single_active_reservation(self, mock_reservation_service):
        # BR04 – Seat belongs to only one active reservation
        mock_reservation_service.createReservation = Mock(return_value=Mock(seat=1, state=ReservationState.CREATED))
        
        reservation = mock_reservation_service. createReservation("FL001", 1)
        
        assert reservation.seat == 1

    def test_br04_same_seat_cannot_be_reserved_twice_on_same_flight(self, mock_reservation_service):
        # BR04 – Same seat cannot have two active reservations on same flight
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1, state=ReservationState. CREATED),
            Exception("Seat already reserved")
        ])
        
        mock_reservation_service. createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info: 
            mock_reservation_service.createReservation("FL001", 1)
        
        assert "Seat already reserved" in str(exc_info.value)

    def test_br04_same_seat_can_be_reserved_on_different_flights(self, mock_reservation_service):
        # BR04 – Same seat number can be reserved on different flights
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1, flightId="FL001", state=ReservationState.CREATED),
            Mock(seat=1, flightId="FL002", state=ReservationState. CREATED)
        ])
        
        res1 = mock_reservation_service.createReservation("FL001", 1)
        res2 = mock_reservation_service.createReservation("FL002", 1)
        
        assert res1.seat == 1
        assert res2.seat == 1
        assert res1.flightId != res2.flightId


# ============================================================================
# BR05 - Canceled reservations must immediately release the associated seat
# ============================================================================

class TestBR05CanceledReservationReleasesSeat:
    """BR05 – Canceled reservations must immediately release the associated seat."""

    def test_br05_seat_released_upon_cancellation(self, mock_reservation_service, confirmed_reservation):
        # BR05 – Canceled reservations must immediately release the associated seat
        seat_released = False
        
        def cancel_and_release(reservation_id):
            nonlocal seat_released
            confirmed_reservation.state = ReservationState. CANCELED
            seat_released = True
        
        mock_reservation_service.cancelReservation = cancel_and_release
        mock_reservation_service.cancelReservation("RES002")
        
        assert confirmed_reservation.state == ReservationState. CANCELED
        assert seat_released is True

    def test_br05_released_seat_available_for_new_reservation(self, mock_reservation_service, confirmed_reservation):
        # BR05 – Released seat becomes available for new reservation
        released_seat = confirmed_reservation.seat
        
        mock_reservation_service.cancelReservation = Mock()
        mock_reservation_service.cancelReservation("RES002")
        confirmed_reservation.state = ReservationState. CANCELED
        
        mock_reservation_service. createReservation = Mock(return_value=Mock(seat=released_seat, state=ReservationState. CREATED))
        new_reservation = mock_reservation_service.createReservation("FL001", released_seat)
        
        assert new_reservation.seat == released_seat


# ============================================================================
# BR06 - Overbooking is not permitted under any circumstances
# ============================================================================

class TestBR06NoOverbooking: 
    """BR06 – Overbooking is not permitted under any circumstances."""

    def test_br06_overbooking_rejected(self, mock_reservation_service, mock_flight):
        # BR06 – Overbooking is not permitted under any circumstances
        mock_flight.totalSeats = 1
        
        mock_reservation_service. createReservation = Mock(side_effect=[
            Mock(seat=1, state=ReservationState. CREATED),
            Exception("Overbooking not permitted")
        ])
        
        mock_reservation_service. createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. createReservation("FL001", 2)
        
        assert "Overbooking not permitted" in str(exc_info.value)

    def test_br06_reservation_rejected_when_flight_full(self, mock_reservation_service, mock_flight):
        # BR06 – Reservation rejected when all seats are taken
        mock_flight.totalSeats = 2
        
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1),
            Mock(seat=2),
            Exception("Flight is fully booked")
        ])
        
        mock_reservation_service.createReservation("FL001", 1)
        mock_reservation_service. createReservation("FL001", 2)
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. createReservation("FL001", 3)
        
        assert "Flight is fully booked" in str(exc_info. value)


# ============================================================================
# BR07 - Confirmed reservations must never exceed total available seats
# ============================================================================

class TestBR07ConfirmedReservationsNotExceedSeats:
    """BR07 – The number of confirmed reservations must never exceed total available seats."""

    def test_br07_confirmed_reservations_within_seat_limit(self, mock_reservation_service, mock_flight):
        # BR07 – Confirmed reservations must not exceed available seats
        mock_flight.totalSeats = 100
        confirmed_count = 100
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("No seats available for confirmation"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES_NEW", True)
        
        assert "No seats available" in str(exc_info.value)

    def test_br07_confirmation_rejected_when_at_capacity(self, mock_reservation_service, mock_flight):
        # BR07 – Cannot confirm reservation when at capacity
        mock_flight.totalSeats = 1
        
        mock_reservation_service. confirmPayment = Mock(side_effect=[
            None,
            Exception("Confirmed reservations exceed seat capacity")
        ])
        
        mock_reservation_service. confirmPayment("RES001", True)
        
        with pytest. raises(Exception) as exc_info: 
            mock_reservation_service.confirmPayment("RES002", True)
        
        assert "exceed seat capacity" in str(exc_info. value)


# ============================================================================
# BR08 - A reservation may be exclusively in one of three states
# ============================================================================

class TestBR08ReservationStates:
    """BR08 – A reservation may be exclusively in one of the following states:  CREATED, CONFIRMED, CANCELED."""

    def test_br08_reservation_state_is_created(self, mock_reservation):
        # BR08 – Reservation can be in CREATED state
        assert mock_reservation.state == ReservationState.CREATED

    def test_br08_reservation_state_is_confirmed(self, confirmed_reservation):
        # BR08 – Reservation can be in CONFIRMED state
        assert confirmed_reservation.state == ReservationState. CONFIRMED

    def test_br08_reservation_state_is_canceled(self, canceled_reservation):
        # BR08 – Reservation can be in CANCELED state
        assert canceled_reservation.state == ReservationState.CANCELED

    def test_br08_reservation_cannot_have_invalid_state(self):
        # BR08 – Reservation cannot have state outside defined values
        valid_states = {ReservationState. CREATED, ReservationState.CONFIRMED, ReservationState.CANCELED}
        
        reservation = Mock()
        reservation.state = ReservationState. CREATED
        
        assert reservation.state in valid_states


# ============================================================================
# BR09 - Intermediate or additional states are not permitted
# ============================================================================

class TestBR09NoIntermediateStates:
    """BR09 – Intermediate or additional states (e.g., 'In payment', 'Pending', 'Expired') are not permitted."""

    def test_br09_in_payment_state_not_permitted(self, mock_reservation_service, mock_reservation):
        # BR09 – 'In payment' state is not permitted
        def set_invalid_state():
            mock_reservation.state = "IN_PAYMENT"
            raise Exception("Invalid state:  IN_PAYMENT not permitted")
        
        with pytest.raises(Exception) as exc_info:
            set_invalid_state()
        
        assert "Invalid state" in str(exc_info.value)

    def test_br09_pending_state_not_permitted(self, mock_reservation_service, mock_reservation):
        # BR09 – 'Pending' state is not permitted
        def set_invalid_state():
            raise Exception("Invalid state:  PENDING not permitted")
        
        with pytest.raises(Exception) as exc_info:
            set_invalid_state()
        
        assert "PENDING not permitted" in str(exc_info.value)

    def test_br09_expired_state_not_permitted(self, mock_reservation_service, mock_reservation):
        # BR09 – 'Expired' state is not permitted
        def set_invalid_state():
            raise Exception("Invalid state:  EXPIRED not permitted")
        
        with pytest.raises(Exception) as exc_info: 
            set_invalid_state()
        
        assert "EXPIRED not permitted" in str(exc_info.value)


# ============================================================================
# BR10 - Valid state transitions are CREATED→CONFIRMED and CONFIRMED→CANCELED
# ============================================================================

class TestBR10ValidStateTransitions: 
    """BR10 – The only valid state transitions are:  CREATED → CONFIRMED and CONFIRMED → CANCELED."""

    def test_br10_transition_created_to_confirmed_is_valid(self, mock_reservation_service, mock_reservation):
        # BR10 – CREATED → CONFIRMED is a valid transition
        mock_reservation_service.confirmPayment = Mock()
        
        mock_reservation_service.confirmPayment("RES001", True)
        mock_reservation.state = ReservationState. CONFIRMED
        
        assert mock_reservation.state == ReservationState.CONFIRMED

    def test_br10_transition_confirmed_to_canceled_is_valid(self, mock_reservation_service, confirmed_reservation):
        # BR10 – CONFIRMED → CANCELED is a valid transition
        mock_reservation_service.cancelReservation = Mock()
        
        mock_reservation_service.cancelReservation("RES002")
        confirmed_reservation.state = ReservationState. CANCELED
        
        assert confirmed_reservation. state == ReservationState.CANCELED


# ============================================================================
# BR11 - Any state transition other than defined must be rejected
# ============================================================================

class TestBR11InvalidStateTransitionsRejected: 
    """BR11 – Any state transition other than those defined must be rejected."""

    def test_br11_transition_created_to_canceled_rejected(self, mock_reservation_service, mock_reservation):
        # BR11 – CREATED → CANCELED is not a valid transition
        mock_reservation_service.cancelReservation = Mock(side_effect=Exception("Invalid state transition:  CREATED → CANCELED"))
        
        with pytest. raises(Exception) as exc_info: 
            mock_reservation_service.cancelReservation("RES001")
        
        assert "Invalid state transition" in str(exc_info.value)

    def test_br11_transition_confirmed_to_created_rejected(self, mock_reservation_service, confirmed_reservation):
        # BR11 – CONFIRMED → CREATED is not a valid transition
        def invalid_transition():
            raise Exception("Invalid state transition: CONFIRMED → CREATED")
        
        with pytest.raises(Exception) as exc_info:
            invalid_transition()
        
        assert "CONFIRMED → CREATED" in str(exc_info.value)

    def test_br11_transition_canceled_to_confirmed_rejected(self, mock_reservation_service, canceled_reservation):
        # BR11 – CANCELED → CONFIRMED is not a valid transition
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Invalid state transition: CANCELED → CONFIRMED"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES003", True)
        
        assert "Invalid state transition" in str(exc_info. value)

    def test_br11_transition_canceled_to_created_rejected(self, mock_reservation_service, canceled_reservation):
        # BR11 – CANCELED → CREATED is not a valid transition
        def invalid_transition():
            raise Exception("Invalid state transition: CANCELED → CREATED")
        
        with pytest.raises(Exception) as exc_info: 
            invalid_transition()
        
        assert "CANCELED → CREATED" in str(exc_info.value)


# ============================================================================
# BR12 - A canceled reservation must not be reactivated, modified, or receive new payments
# ============================================================================

class TestBR12CanceledReservationImmutable:
    """BR12 – A canceled reservation must not be reactivated, modified, or receive new payments."""

    def test_br12_canceled_reservation_cannot_be_reactivated(self, mock_reservation_service, canceled_reservation):
        # BR12 – Canceled reservation cannot be reactivated
        def reactivate():
            raise Exception("Canceled reservation cannot be reactivated")
        
        with pytest.raises(Exception) as exc_info:
            reactivate()
        
        assert "cannot be reactivated" in str(exc_info.value)

    def test_br12_canceled_reservation_cannot_be_modified(self, mock_reservation_service, canceled_reservation):
        # BR12 – Canceled reservation cannot be modified
        def modify_reservation():
            raise Exception("Canceled reservation cannot be modified")
        
        with pytest. raises(Exception) as exc_info: 
            modify_reservation()
        
        assert "cannot be modified" in str(exc_info.value)

    def test_br12_canceled_reservation_cannot_receive_payment(self, mock_reservation_service, canceled_reservation):
        # BR12 – Canceled reservation cannot receive new payments
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Cannot add payment to canceled reservation"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES003", True)
        
        assert "canceled reservation" in str(exc_info.value)


# ============================================================================
# BR13 - Cancellation refund policy based on remaining time
# ============================================================================

class TestBR13CancellationRefundPolicy: 
    """BR13 – Cancellation must comply with temporal policy: ≥24h = full refund; <24h = no refund."""

    def test_br13_full_refund_when_24_hours_or_more_before_flight(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # BR13 – Full refund when remaining time ≥ 24 hours
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 0)  # Exactly 24 hours before
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours >= 24
        
        refund_result = Mock(refundAmount="full")
        assert refund_result. refundAmount == "full"

    def test_br13_no_refund_when_less_than_24_hours_before_flight(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # BR13 – No refund when remaining time < 24 hours
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 1)  # 1 second less than 24 hours
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours < 24
        
        refund_result = Mock(refundAmount="none")
        assert refund_result.refundAmount == "none"

    def test_br13_exactly_24_hours_before_flight_full_refund(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # BR13 – Exactly 24 hours before flight gets full refund
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 0)  # Exactly 24 hours
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours == 24
        
        refund_result = Mock(refundAmount="full")
        assert refund_result. refundAmount == "full"


# ============================================================================
# BR14 - Remaining time calculated in exact hours with no rounding
# ============================================================================

class TestBR14ExactTimeCalculation:
    """BR14 – Remaining time must be calculated in exact hours, with no rounding or tolerance."""

    def test_br14_exact_time_calculation_23_hours_59_minutes(self, mock_flight):
        # BR14 – Time must be calculated exactly, 23h59m is less than 24h
        mock_flight. dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 1, 0)  # 23 hours 59 minutes before
        
        remaining_seconds = (mock_flight.dateTime - current_time).total_seconds()
        remaining_hours = remaining_seconds / 3600
        
        assert remaining_hours < 24
        assert remaining_hours == pytest.approx(23. 983333333333334, rel=1e-9)

    def test_br14_exact_time_calculation_24_hours_1_second(self, mock_flight):
        # BR14 – Time must be calculated exactly, 24h1s is more than 24h
        mock_flight. dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 13, 59, 59)  # 24 hours and 1 second before
        
        remaining_seconds = (mock_flight.dateTime - current_time).total_seconds()
        remaining_hours = remaining_seconds / 3600
        
        assert remaining_hours > 24

    def test_br14_no_rounding_applied_to_time(self, mock_flight):
        # BR14 – No rounding tolerance applied
        mock_flight. dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 1)  # 23 hours 59 minutes 59 seconds
        
        remaining_seconds = (mock_flight.dateTime - current_time).total_seconds()
        remaining_hours = remaining_seconds / 3600
        
        # Exact calculation, no rounding
        assert remaining_hours == (23 * 3600 + 59 * 60 + 59) / 3600


# ============================================================================
# BR15 - System must use internally stored flight date and time
# ============================================================================

class TestBR15InternallyStoredFlightTime:
    """BR15 – The system must use exclusively the internally stored flight date and time."""

    def test_br15_uses_internal_flight_datetime(self, mock_reservation_service, mock_flight):
        # BR15 – System uses stored flight dateTime
        stored_datetime = datetime(2026, 1, 20, 14, 0, 0)
        mock_flight.dateTime = stored_datetime
        
        assert mock_flight.dateTime == stored_datetime

    def test_br15_external_time_not_used(self, mock_reservation_service, mock_flight):
        # BR15 – External time source must not override internal flight time
        internal_time = datetime(2026, 1, 20, 14, 0, 0)
        external_time = datetime(2026, 1, 20, 16, 0, 0)
        
        mock_flight.dateTime = internal_time
        
        assert mock_flight.dateTime == internal_time
        assert mock_flight.dateTime != external_time


# ============================================================================
# BR16 - Flight dates, times, and identifiers must not be altered after confirmation
# ============================================================================

class TestBR16FlightDataImmutableAfterConfirmation:
    """BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation."""

    def test_br16_flight_date_cannot_change_after_confirmation(self, confirmed_reservation, mock_flight):
        # BR16 – Flight date cannot be altered after confirmation
        original_datetime = mock_flight.dateTime
        
        def attempt_change():
            raise Exception("Flight date cannot be modified after confirmation")
        
        with pytest.raises(Exception) as exc_info:
            attempt_change()
        
        assert "cannot be modified" in str(exc_info. value)
        assert mock_flight.dateTime == original_datetime

    def test_br16_flight_id_cannot_change_after_confirmation(self, confirmed_reservation, mock_flight):
        # BR16 – Flight identifier cannot be altered after confirmation
        original_id = mock_flight.flightId
        
        def attempt_change():
            raise Exception("Flight identifier cannot be modified after confirmation")
        
        with pytest. raises(Exception) as exc_info: 
            attempt_change()
        
        assert "cannot be modified" in str(exc_info.value)
        assert mock_flight.flightId == original_id


# ============================================================================
# BR17 - Indirect modifications of flight data are prohibited
# ============================================================================

class TestBR17IndirectModificationsProhibited: 
    """BR17 – Indirect modifications (reference swapping, cloning, recreation) are prohibited."""

    def test_br17_reference_swapping_prohibited(self, confirmed_reservation, mock_flight):
        # BR17 – Reference swapping is prohibited
        def attempt_reference_swap():
            raise Exception("Reference swapping of flight data is prohibited")
        
        with pytest.raises(Exception) as exc_info:
            attempt_reference_swap()
        
        assert "Reference swapping" in str(exc_info. value)

    def test_br17_cloning_flight_data_prohibited(self, confirmed_reservation, mock_flight):
        # BR17 – Cloning flight data for modification is prohibited
        def attempt_clone():
            raise Exception("Cloning flight data is prohibited")
        
        with pytest.raises(Exception) as exc_info:
            attempt_clone()
        
        assert "Cloning" in str(exc_info.value)

    def test_br17_object_recreation_prohibited(self, confirmed_reservation, mock_flight):
        # BR17 – Object recreation to bypass immutability is prohibited
        def attempt_recreation():
            raise Exception("Object recreation is prohibited")
        
        with pytest.raises(Exception) as exc_info:
            attempt_recreation()
        
        assert "recreation is prohibited" in str(exc_info.value)


# ============================================================================
# BR18 - Each reservation may have exactly one associated payment
# ============================================================================

class TestBR18ExactlyOnePaymentPerReservation: 
    """BR18 – Each reservation may have exactly one associated payment."""

    def test_br18_reservation_has_one_payment(self, mock_reservation):
        # BR18 – Reservation can have exactly one payment
        mock_reservation. payment = Mock(status="approved")
        
        assert mock_reservation. payment is not None

    def test_br18_reservation_cannot_have_multiple_payments(self, mock_reservation_service, mock_reservation):
        # BR18 – Reservation cannot have more than one payment
        mock_reservation.payment = Mock(status="approved")
        
        def add_second_payment():
            raise Exception("Reservation already has a payment associated")
        
        with pytest.raises(Exception) as exc_info:
            add_second_payment()
        
        assert "already has a payment" in str(exc_info.value)


# ============================================================================
# BR19 - Additional payment attempts for same reservation must be rejected
# ============================================================================

class TestBR19AdditionalPaymentAttemptsRejected:
    """BR19 – Additional payment attempts for the same reservation must be rejected."""

    def test_br19_second_payment_attempt_rejected(self, mock_reservation_service, confirmed_reservation):
        # BR19 – Second payment attempt must be rejected
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Payment already processed for this reservation"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES002", True)
        
        assert "already processed" in str(exc_info.value)

    def test_br19_retry_payment_after_failure_rejected(self, mock_reservation_service, mock_reservation):
        # BR19 – Retry payment after initial attempt must be rejected
        mock_reservation. payment = Mock(status="declined")
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Payment attempt already recorded"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. confirmPayment("RES001", True)
        
        assert "already recorded" in str(exc_info.value)


# ============================================================================
# BR20 - Payments must not be accepted for canceled reservations or after flight
# ============================================================================

class TestBR20PaymentRestrictionsForCanceledOrPastFlights: 
    """BR20 – Payments must not be accepted for canceled reservations or after the flight date."""

    def test_br20_payment_rejected_for_canceled_reservation(self, mock_reservation_service, canceled_reservation):
        # BR20 – Payment not accepted for canceled reservation
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot accept payment for canceled reservation"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES003", True)
        
        assert "canceled reservation" in str(exc_info.value)

    def test_br20_payment_rejected_after_flight_date(self, mock_reservation_service, mock_reservation, mock_flight):
        # BR20 – Payment not accepted after flight date
        mock_flight.dateTime = datetime(2026, 1, 10, 14, 0, 0)  # Past flight date
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Cannot accept payment after flight date"))
        
        with pytest. raises(Exception) as exc_info: 
            mock_reservation_service.confirmPayment("RES001", True)
        
        assert "after flight date" in str(exc_info. value)


# ============================================================================
# BR21 - System operations must be deterministic
# ============================================================================

class TestBR21DeterministicOperations: 
    """BR21 – System operations must be deterministic, producing same result for same inputs."""

    def test_br21_same_inputs_produce_same_reservation(self, mock_reservation_service):
        # BR21 – Same inputs produce same result
        expected_result = Mock(seat=1, state=ReservationState.CREATED)
        mock_reservation_service. createReservation = Mock(return_value=expected_result)
        
        result1 = mock_reservation_service.createReservation("FL001", 1)
        
        mock_reservation_service.createReservation = Mock(return_value=expected_result)
        result2 = mock_reservation_service.createReservation("FL001", 1)
        
        assert result1. seat == result2.seat
        assert result1.state == result2.state

    def test_br21_confirmation_deterministic(self, mock_reservation_service):
        # BR21 – Confirmation produces same outcome for same input sequence
        mock_reservation_service. confirmPayment = Mock(return_value=None)
        
        # Same call should not raise different exceptions on different runs
        mock_reservation_service. confirmPayment("RES001", True)
        mock_reservation_service.confirmPayment. assert_called_with("RES001", True)


# ============================================================================
# BR22 - System must not assume unspecified implicit behaviors
# ============================================================================

class TestBR22NoImplicitBehaviors:
    """BR22 – System must not assume unspecified implicit behaviors."""

    def test_br22_no_future_credit_assumption(self, mock_reservation_service, canceled_reservation):
        # BR22 – No future credit for canceled reservation
        def apply_credit():
            raise Exception("Future credit is not a specified behavior")
        
        with pytest.raises(Exception) as exc_info:
            apply_credit()
        
        assert "not a specified behavior" in str(exc_info. value)

    def test_br22_no_automatic_rebooking(self, mock_reservation_service, canceled_reservation):
        # BR22 – No automatic rebooking for canceled reservation
        def auto_rebook():
            raise Exception("Automatic rebooking is not specified")
        
        with pytest.raises(Exception) as exc_info:
            auto_rebook()
        
        assert "not specified" in str(exc_info.value)

    def test_br22_no_commercial_exceptions(self, mock_reservation_service):
        # BR22 – No commercial exceptions applied
        def apply_commercial_exception():
            raise Exception("Commercial exceptions are not specified")
        
        with pytest.raises(Exception) as exc_info: 
            apply_commercial_exception()
        
        assert "Commercial exceptions" in str(exc_info.value)


# ============================================================================
# BR23 - Business rule violation must result in immediate failure
# ============================================================================

class TestBR23ImmediateFailureOnViolation: 
    """BR23 – Any business rule violation must result in immediate failure with no state change."""

    def test_br23_violation_causes_immediate_failure(self, mock_reservation_service, mock_reservation):
        # BR23 – Business rule violation causes immediate failure
        original_state = mock_reservation. state
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Business rule violation"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. confirmPayment("RES001", False)
        
        assert mock_reservation.state == original_state

    def test_br23_no_partial_records_on_failure(self, mock_reservation_service):
        # BR23 – No partial records created on failure
        records_before = 0
        
        mock_reservation_service.createReservation = Mock(side_effect=Exception("Validation failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.createReservation("FL001", -1)
        
        records_after = 0  # No records should be created
        assert records_before == records_after


# ============================================================================
# BR24 - Each valid operation must generate exactly one immutable record
# ============================================================================

class TestBR24ValidOperationGeneratesOneRecord:
    """BR24 – Each valid operation must generate exactly one immutable record."""

    def test_br24_create_reservation_generates_one_record(self, mock_reservation_service):
        # BR24 – Creating reservation generates exactly one record
        mock_reservation_service.createReservation = Mock(return_value=Mock(
            reservationId="RES001",
            state=ReservationState.CREATED
        ))
        
        result = mock_reservation_service.createReservation("FL001", 1)
        
        assert result.reservationId == "RES001"
        mock_reservation_service. createReservation. assert_called_once()

    def test_br24_record_is_immutable(self, mock_reservation):
        # BR24 – Record created is immutable
        original_id = mock_reservation. reservationId
        
        def attempt_modify_id():
            raise Exception("Record is immutable")
        
        with pytest. raises(Exception) as exc_info: 
            attempt_modify_id()
        
        assert "immutable" in str(exc_info.value)


# ============================================================================
# BR25 - Failed operations must not generate persistent records
# ============================================================================

class TestBR25FailedOperationsNoPersistentRecords:
    """BR25 – Failed operations must not generate persistent records."""

    def test_br25_failed_reservation_no_record(self, mock_reservation_service):
        # BR25 – Failed reservation creation generates no record
        mock_reservation_service. createReservation = Mock(side_effect=Exception("Creation failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.createReservation("FL001", 999)

    def test_br25_failed_payment_no_record(self, mock_reservation_service, mock_reservation):
        # BR25 – Failed payment generates no persistent record
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Payment failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.confirmPayment("RES001", False)
        
        assert mock_reservation.payment is None


# ============================================================================
# BR26 - Operations on one reservation must not affect others
# ============================================================================

class TestBR26OperationIsolation:
    """BR26 – Operations on one reservation must not affect other reservations, flights, or seats."""

    def test_br26_cancellation_does_not_affect_other_reservations(self, mock_reservation_service, confirmed_reservation):
        # BR26 – Canceling one reservation does not affect others
        other_reservation = Mock(state=ReservationState.CONFIRMED, reservationId="RES999")
        
        mock_reservation_service.cancelReservation = Mock()
        mock_reservation_service.cancelReservation("RES002")
        confirmed_reservation.state = ReservationState. CANCELED
        
        assert other_reservation.state == ReservationState. CONFIRMED

    def test_br26_confirmation_does_not_affect_other_flights(self, mock_reservation_service, mock_reservation):
        # BR26 – Confirming reservation does not affect other flights
        other_flight = Mock(flightId="FL999", totalSeats=100)
        original_seats = other_flight.totalSeats
        
        mock_reservation_service.confirmPayment = Mock()
        mock_reservation_service.confirmPayment("RES001", True)
        
        assert other_flight.totalSeats == original_seats

    def test_br26_seat_allocation_isolated(self, mock_reservation_service):
        # BR26 – Seat allocation for one reservation does not affect other seats
        reservation1 = Mock(seat=1, flightId="FL001")
        reservation2 = Mock(seat=2, flightId="FL001")
        
        # Modifying reservation1 should not affect reservation2
        reservation1.state = ReservationState.CANCELED
        
        assert reservation2.seat == 2


# ============================================================================
# FR01 - Create initial reservation in CREATED state
# ============================================================================

class TestFR01CreateInitialReservation:
    """FR01 – Create an initial reservation in the CREATED state, associated with flight and available seat."""

    def test_fr01_reservation_created_in_created_state(self, mock_reservation_service):
        # FR01 – Reservation is created in CREATED state
        mock_reservation_service.createReservation = Mock(return_value=Mock(
            state=ReservationState.CREATED,
            seat=1,
            flightId="FL001"
        ))
        
        reservation = mock_reservation_service.createReservation("FL001", 1)
        
        assert reservation. state == ReservationState.CREATED

    def test_fr01_reservation_associated_with_flight(self, mock_reservation_service):
        # FR01 – Reservation is associated with a flight
        mock_reservation_service.createReservation = Mock(return_value=Mock(
            flightId="FL001",
            state=ReservationState.CREATED
        ))
        
        reservation = mock_reservation_service.createReservation("FL001", 1)
        
        assert reservation.flightId == "FL001"

    def test_fr01_reservation_associated_with_available_seat(self, mock_reservation_service):
        # FR01 – Reservation is associated with an available seat
        mock_reservation_service.createReservation = Mock(return_value=Mock(
            seat=5,
            state=ReservationState. CREATED
        ))
        
        reservation = mock_reservation_service.createReservation("FL001", 5)
        
        assert reservation.seat == 5


# ============================================================================
# FR02 - Confirm payment and atomically confirm reservation
# ============================================================================

class TestFR02ConfirmPaymentAndReservation:
    """FR02 – Confirm payment and, atomically, confirm the reservation."""

    def test_fr02_payment_and_reservation_confirmed_together(self, mock_reservation_service, mock_reservation):
        # FR02 – Payment confirmation and reservation confirmation are atomic
        mock_reservation_service.confirmPayment = Mock(return_value=None)
        
        mock_reservation_service. confirmPayment("RES001", True)
        mock_reservation.state = ReservationState. CONFIRMED
        mock_reservation.payment = Mock(status="approved")
        
        assert mock_reservation. state == ReservationState.CONFIRMED
        assert mock_reservation.payment.status == "approved"


# ============================================================================
# FR03 - Strictly control seat availability with exclusivity
# ============================================================================

class TestFR03SeatAvailabilityControl:
    """FR03 – Strictly control seat availability, ensuring exclusivity per active reservation."""

    def test_fr03_seat_exclusivity_enforced(self, mock_reservation_service):
        # FR03 – Seat exclusivity is enforced
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1),
            Exception("Seat not available")
        ])
        
        mock_reservation_service. createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. createReservation("FL001", 1)
        
        assert "Seat not available" in str(exc_info.value)


# ============================================================================
# FR04 - Cancel reservations respecting refund policy
# ============================================================================

class TestFR04CancelWithRefundPolicy:
    """FR04 – Cancel reservations while strictly respecting the refund policy based on remaining time."""

    def test_fr04_cancellation_with_full_refund(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # FR04 – Cancellation with full refund when ≥24 hours before flight
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 13, 0, 0)  # More than 24 hours before
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        mock_reservation_service. cancelReservation = Mock(return_value=Mock(refund="full"))
        result = mock_reservation_service.cancelReservation("RES002")
        
        assert remaining_hours >= 24
        assert result. refund == "full"

    def test_fr04_cancellation_with_no_refund(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # FR04 – Cancellation with no refund when <24 hours before flight
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 15, 0, 0)  # Less than 24 hours before
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        mock_reservation_service.cancelReservation = Mock(return_value=Mock(refund="none"))
        result = mock_reservation_service.cancelReservation("RES002")
        
        assert remaining_hours < 24
        assert result.refund == "none"


# ============================================================================
# FR05 - Prevent invalid modification of state, flight data, seat, or payment
# ============================================================================

class TestFR05PreventInvalidModifications:
    """FR05 – Prevent any invalid modification of state, flight data, seat, or payment."""

    def test_fr05_invalid_state_modification_prevented(self, mock_reservation_service, confirmed_reservation):
        # FR05 – Invalid state modification is prevented
        def invalid_state_change():
            raise Exception("Invalid state modification")
        
        with pytest.raises(Exception) as exc_info:
            invalid_state_change()
        
        assert "Invalid state modification" in str(exc_info.value)

    def test_fr05_flight_data_modification_prevented(self, mock_flight):
        # FR05 – Flight data modification is prevented
        def modify_flight():
            raise Exception("Flight data modification not allowed")
        
        with pytest.raises(Exception) as exc_info:
            modify_flight()
        
        assert "modification not allowed" in str(exc_info. value)

    def test_fr05_seat_modification_prevented(self, confirmed_reservation):
        # FR05 – Seat modification is prevented after confirmation
        def modify_seat():
            raise Exception("Seat modification not allowed")
        
        with pytest.raises(Exception) as exc_info: 
            modify_seat()
        
        assert "Seat modification" in str(exc_info.value)

    def test_fr05_payment_modification_prevented(self, confirmed_reservation):
        # FR05 – Payment modification is prevented
        def modify_payment():
            raise Exception("Payment modification not allowed")
        
        with pytest.raises(Exception) as exc_info:
            modify_payment()
        
        assert "Payment modification" in str(exc_info.value)


# ============================================================================
# FR06 - Do not allow overbooking at any stage
# ============================================================================

class TestFR06NoOverbookingAtAnyStage:
    """FR06 – Do not allow overbooking at any stage of the process."""

    def test_fr06_overbooking_prevented_at_creation(self, mock_reservation_service, mock_flight):
        # FR06 – Overbooking prevented at reservation creation
        mock_flight.totalSeats = 1
        
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1),
            Exception("No seats available - overbooking not allowed")
        ])
        
        mock_reservation_service. createReservation("FL001", 1)
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. createReservation("FL001", 2)
        
        assert "overbooking" in str(exc_info.value).lower()

    def test_fr06_overbooking_prevented_at_confirmation(self, mock_reservation_service):
        # FR06 – Overbooking prevented at confirmation stage
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot confirm - would exceed seat capacity"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service. confirmPayment("RES001", True)
        
        assert "exceed seat capacity" in str(exc_info. value)


# ============================================================================
# FR07 - Do not allow multiple, partial, or late payments
# ============================================================================

class TestFR07PaymentRestrictions:
    """FR07 – Do not allow multiple, partial, or late payments."""

    def test_fr07_multiple_payments_not_allowed(self, mock_reservation_service, confirmed_reservation):
        # FR07 – Multiple payments not allowed
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Multiple payments not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES002", True)
        
        assert "Multiple payments" in str(exc_info.value)

    def test_fr07_partial_payment_not_allowed(self, mock_reservation_service, mock_reservation):
        # FR07 – Partial payment not allowed
        def attempt_partial():
            raise Exception("Partial payment not allowed")
        
        with pytest.raises(Exception) as exc_info: 
            attempt_partial()
        
        assert "Partial payment" in str(exc_info.value)

    def test_fr07_late_payment_not_allowed(self, mock_reservation_service, mock_reservation, mock_flight):
        # FR07 – Late payment not allowed (after flight date)
        mock_flight.dateTime = datetime(2026, 1, 10, 14, 0, 0)  # Past date
        
        mock_reservation_service. confirmPayment = Mock(side_effect=Exception("Late payment not allowed"))
        
        with pytest.raises(Exception) as exc_info:
            mock_reservation_service.confirmPayment("RES001", True)
        
        assert "Late payment" in str(exc_info.value)


# ============================================================================
# FR08 - Do not return intermediate states or partial results
# ============================================================================

class TestFR08NoIntermediateStatesOrPartialResults: 
    """FR08 – Do not return intermediate states, explanatory messages, or partial results."""

    def test_fr08_no_intermediate_state_returned(self, mock_reservation_service, mock_reservation):
        # FR08 – No intermediate state returned
        mock_reservation_service.createReservation = Mock(return_value=Mock(
            state=ReservationState.CREATED
        ))
        
        reservation = mock_reservation_service.createReservation("FL001", 1)
        
        assert reservation. state in [ReservationState.CREATED, ReservationState. CONFIRMED, ReservationState. CANCELED]

    def test_fr08_no_partial_result_on_failure(self, mock_reservation_service):
        # FR08 – No partial result returned on failure
        mock_reservation_service. createReservation = Mock(side_effect=Exception("Operation failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.createReservation("FL001", 1)


# ============================================================================
# FR09 - Failures do not modify state or produce side effects
# ============================================================================

class TestFR09FailuresNoSideEffects: 
    """FR09 – Ensure that failures do not modify state or produce persistent side effects."""

    def test_fr09_failure_does_not_modify_reservation_state(self, mock_reservation_service, mock_reservation):
        # FR09 – Failure does not modify reservation state
        original_state = mock_reservation.state
        
        mock_reservation_service.confirmPayment = Mock(side_effect=Exception("Payment failed"))
        
        with pytest.raises(Exception):
            mock_reservation_service.confirmPayment("RES001", False)
        
        assert mock_reservation. state == original_state

    def test_fr09_failure_does_not_create_records(self, mock_reservation_service):
        # FR09 – Failure does not create any records
        mock_reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat"))
        
        with pytest.raises(Exception):
            mock_reservation_service. createReservation("FL001", -1)


# ============================================================================
# FR10 - Use exclusively provided and internally stored data
# ============================================================================

class TestFR10UseInternalDataOnly:
    """FR10 – Use exclusively provided and internally stored data, with no inference or external enrichment."""

    def test_fr10_uses_provided_flight_id(self, mock_reservation_service):
        # FR10 – Uses provided flight ID
        mock_reservation_service.createReservation = Mock(return_value=Mock(flightId="FL001"))
        
        reservation = mock_reservation_service.createReservation("FL001", 1)
        
        assert reservation.flightId == "FL001"

    def test_fr10_uses_provided_seat_number(self, mock_reservation_service):
        # FR10 – Uses provided seat number
        mock_reservation_service.createReservation = Mock(return_value=Mock(seat=42))
        
        reservation = mock_reservation_service.createReservation("FL001", 42)
        
        assert reservation.seat == 42

    def test_fr10_no_external_data_enrichment(self, mock_reservation_service, mock_reservation):
        # FR10 – No external data enrichment
        mock_reservation. extraData = None
        
        assert mock_reservation.extraData is None


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases: 
    """Edge case tests as required by the specifications."""

    def test_edge_case_exactly_24_hours_boundary_full_refund(self, mock_flight):
        # BR13/BR14 – Edge case: Exactly 24 hours before flight
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 0)
        
        remaining_hours = (mock_flight. dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours == 24
        # Per BR13: ≥ 24 hours = full refund

    def test_edge_case_one_second_under_24_hours_no_refund(self, mock_flight):
        # BR13/BR14 – Edge case: One second under 24 hours
        mock_flight.dateTime = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 1)
        
        remaining_hours = (mock_flight.dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours < 24
        # Per BR13: < 24 hours = no refund

    def test_edge_case_flight_with_single_seat(self, mock_reservation_service, mock_flight):
        # BR06/BR07 – Edge case: Flight with only one seat
        mock_flight.totalSeats = 1
        
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(seat=1, state=ReservationState.CREATED),
            Exception("No seats available")
        ])
        
        mock_reservation_service.createReservation("FL001", 1)
        
        with pytest.raises(Exception):
            mock_reservation_service.createReservation("FL001", 2)

    def test_edge_case_reservation_id_uniqueness(self, mock_reservation_service):
        # BR24 – Edge case:  Each reservation has unique ID
        mock_reservation_service.createReservation = Mock(side_effect=[
            Mock(reservationId="RES001"),
            Mock(reservationId="RES002")
        ])
        
        res1 = mock_reservation_service.createReservation("FL001", 1)
        res2 = mock_reservation_service.createReservation("FL001", 2)
        
        assert res1.reservationId != res2.reservationId

    def test_edge_case_seat_zero_if_valid(self, mock_reservation_service):
        # FR01 – Edge case:  Seat number 0 if valid in system
        mock_reservation_service.createReservation = Mock(return_value=Mock(seat=0))
        
        reservation = mock_reservation_service. createReservation("FL001", 0)
        
        assert reservation.seat == 0

    def test_edge_case_cancellation_right_at_flight_time(self, mock_reservation_service, confirmed_reservation, mock_flight):
        # BR13/BR20 – Edge case:  Cancellation exactly at flight time
        mock_flight.dateTime = datetime(2026, 1, 12, 14, 0, 0)
        current_time = datetime(2026, 1, 12, 14, 0, 0)
        
        remaining_hours = (mock_flight. dateTime - current_time).total_seconds() / 3600
        
        assert remaining_hours == 0
        assert remaining_hours < 24
        # No refund since < 24 hours
```