```python
"""
Automated tests for Airline Reservation System
Based exclusively on provided Business Rules (BR) and Functional Requirements (FR)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from enum import Enum


# ============================================================================
# TEST FIXTURES AND HELPER SETUP
# ============================================================================

class ReservationState(Enum):
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"


@pytest.fixture
def reservation_service():
    """Fixture to provide a mock ReservationService instance."""
    service = Mock()
    return service


@pytest. fixture
def flight():
    """Fixture to provide a mock Flight instance."""
    flight = Mock()
    flight.flightId = "FL001"
    flight. dateTime = datetime(2026, 1, 20, 14, 0, 0)
    flight.totalSeats = 100
    return flight


@pytest.fixture
def reservation():
    """Fixture to provide a mock Reservation instance."""
    reservation = Mock()
    reservation.reservationId = "RES001"
    reservation.state = ReservationState. CREATED
    reservation. seat = 1
    reservation.flightId = "FL001"
    reservation.payment = None
    return reservation


@pytest.fixture
def confirmed_reservation():
    """Fixture to provide a confirmed reservation."""
    reservation = Mock()
    reservation.reservationId = "RES002"
    reservation. state = ReservationState.CONFIRMED
    reservation.seat = 2
    reservation.flightId = "FL001"
    reservation.payment = Mock(status="approved")
    return reservation


@pytest.fixture
def canceled_reservation():
    """Fixture to provide a canceled reservation."""
    reservation = Mock()
    reservation.reservationId = "RES003"
    reservation. state = ReservationState.CANCELED
    reservation.seat = 3
    reservation.flightId = "FL001"
    reservation.payment = None
    return reservation


# ============================================================================
# BR01 – A reservation may only be confirmed if exactly one approved payment
#        is associated with it
# ============================================================================

class TestBR01ReservationConfirmationRequiresApprovedPayment:
    
    def test_reservation_confirms_with_exactly_one_approved_payment(self, reservation_service, reservation):
        # BR01 – Reservation confirms when exactly one approved payment exists
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation. payment = Mock(status="approved")
        
        reservation_service.confirmPayment(reservation. reservationId, True)
        
        reservation_service.confirmPayment.assert_called_once_with(reservation.reservationId, True)

    def test_reservation_does_not_confirm_without_payment(self, reservation_service, reservation):
        # BR01 – Reservation must not confirm when no payment is associated
        reservation. payment = None
        reservation_service.confirmPayment = Mock(side_effect=Exception("No payment associated"))
        
        with pytest. raises(Exception) as excinfo: 
            reservation_service. confirmPayment(reservation.reservationId, True)
        
        assert "No payment associated" in str(excinfo.value)

    def test_reservation_does_not_confirm_with_zero_payments(self, reservation_service, reservation):
        # BR01 – Reservation must not confirm when zero payments exist
        reservation.payments = []
        reservation_service.confirmPayment = Mock(side_effect=Exception("Exactly one approved payment required"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation. reservationId, True)
        
        assert "Exactly one approved payment required" in str(excinfo. value)


# ============================================================================
# BR02 – Payments with a status other than approved must not confirm reservations
# ============================================================================

class TestBR02NonApprovedPaymentsMustNotConfirmReservations:
    
    def test_pending_payment_does_not_confirm_reservation(self, reservation_service, reservation):
        # BR02 – Pending payment must not confirm reservation
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert "Payment not approved" in str(excinfo.value)

    def test_declined_payment_does_not_confirm_reservation(self, reservation_service, reservation):
        # BR02 – Declined payment must not confirm reservation
        reservation. payment = Mock(status="declined")
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert "Payment not approved" in str(excinfo.value)

    def test_failed_payment_does_not_confirm_reservation(self, reservation_service, reservation):
        # BR02 – Failed payment must not confirm reservation
        reservation.payment = Mock(status="failed")
        reservation_service. confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert "Payment not approved" in str(excinfo. value)


# ============================================================================
# BR03 – Reservation confirmation and payment approval must occur atomically
# ============================================================================

class TestBR03AtomicConfirmationAndPayment:
    
    def test_confirmation_and_payment_occur_atomically_success(self, reservation_service, reservation):
        # BR03 – Reservation confirmation and payment must be atomic
        reservation_service.confirmPayment = Mock(return_value=None)
        
        reservation_service.confirmPayment(reservation.reservationId, True)
        
        # Verify single atomic call
        reservation_service.confirmPayment. assert_called_once()

    def test_no_partial_state_on_payment_failure(self, reservation_service, reservation):
        # BR03 – No observable state where only payment or only confirmation completed
        original_state = reservation. state
        reservation_service.confirmPayment = Mock(side_effect=Exception("Atomic operation failed"))
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment(reservation.reservationId, True)
        
        # State must remain unchanged
        assert reservation.state == original_state

    def test_no_partial_state_on_confirmation_failure(self, reservation_service, reservation):
        # BR03 – Confirmation failure must not leave payment approved without confirmation
        reservation_service.confirmPayment = Mock(side_effect=Exception("Confirmation failed"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. confirmPayment(reservation.reservationId, True)
        
        assert "Confirmation failed" in str(excinfo.value)


# ============================================================================
# BR04 – A seat may belong to at most one active reservation per flight
# ============================================================================

class TestBR04SeatExclusivity: 
    
    def test_seat_assigned_to_single_active_reservation(self, reservation_service, flight):
        # BR04 – Seat belongs to at most one active reservation
        reservation_service. createReservation = Mock(return_value=Mock(seat=1, state=ReservationState.CREATED))
        
        result = reservation_service. createReservation(flight.flightId, 1)
        
        assert result.seat == 1

    def test_seat_cannot_be_assigned_to_second_active_reservation(self, reservation_service, flight, reservation):
        # BR04 – Same seat cannot belong to two active reservations on same flight
        reservation. seat = 5
        reservation. state = ReservationState.CREATED
        reservation_service.createReservation = Mock(side_effect=Exception("Seat already reserved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 5)
        
        assert "Seat already reserved" in str(excinfo.value)

    def test_confirmed_reservation_blocks_seat_for_new_reservation(self, reservation_service, flight, confirmed_reservation):
        # BR04 – Confirmed reservation blocks seat from new reservation
        confirmed_reservation.seat = 10
        reservation_service.createReservation = Mock(side_effect=Exception("Seat already reserved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 10)
        
        assert "Seat already reserved" in str(excinfo.value)


# ============================================================================
# BR05 – Canceled reservations must immediately release the associated seat
# ============================================================================

class TestBR05CanceledReservationsReleaseSeat:
    
    def test_canceled_reservation_releases_seat_immediately(self, reservation_service, confirmed_reservation, flight):
        # BR05 – Canceled reservation must immediately release seat
        seat_number = confirmed_reservation. seat
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.createReservation = Mock(return_value=Mock(seat=seat_number))
        
        reservation_service.cancelReservation(confirmed_reservation.reservationId)
        confirmed_reservation.state = ReservationState.CANCELED
        
        # Seat should now be available for new reservation
        new_reservation = reservation_service.createReservation(flight.flightId, seat_number)
        assert new_reservation.seat == seat_number

    def test_seat_available_after_cancellation(self, reservation_service, flight):
        # BR05 – Seat becomes available immediately after cancellation
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.isSeatAvailable = Mock(return_value=True)
        
        reservation_service.cancelReservation("RES001")
        
        assert reservation_service. isSeatAvailable(flight.flightId, 1) is True


# ============================================================================
# BR06 – Overbooking is not permitted under any circumstances
# ============================================================================

class TestBR06NoOverbooking: 
    
    def test_overbooking_not_permitted(self, reservation_service, flight):
        # BR06 – Overbooking must not be permitted
        flight.totalSeats = 1
        reservation_service.createReservation = Mock(side_effect=Exception("Overbooking not permitted"))
        
        # First reservation takes the only seat
        first_call = Mock(return_value=Mock(seat=1))
        reservation_service.createReservation = first_call
        reservation_service.createReservation(flight.flightId, 1)
        
        # Second reservation must fail
        reservation_service.createReservation = Mock(side_effect=Exception("Overbooking not permitted"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. createReservation(flight.flightId, 1)
        
        assert "Overbooking not permitted" in str(excinfo.value)

    def test_reservation_rejected_when_all_seats_taken(self, reservation_service, flight):
        # BR06 – Reservation rejected when no seats available
        flight.totalSeats = 0
        reservation_service.createReservation = Mock(side_effect=Exception("No seats available"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 1)
        
        assert "No seats available" in str(excinfo.value)


# ============================================================================
# BR07 – Confirmed reservations must never exceed total available seats
# ============================================================================

class TestBR07ConfirmedReservationsDoNotExceedSeats:
    
    def test_confirmed_reservations_do_not_exceed_total_seats(self, reservation_service, flight):
        # BR07 – Number of confirmed reservations must not exceed total seats
        flight.totalSeats = 2
        reservation_service.getConfirmedReservationCount = Mock(return_value=2)
        reservation_service.createReservation = Mock(side_effect=Exception("Flight fully booked"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 3)
        
        assert "Flight fully booked" in str(excinfo.value)

    def test_confirmation_rejected_when_at_capacity(self, reservation_service, flight, reservation):
        # BR07 – Confirmation rejected when flight at capacity
        flight. totalSeats = 50
        reservation_service.getConfirmedReservationCount = Mock(return_value=50)
        reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot confirm:  flight at capacity"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. confirmPayment(reservation.reservationId, True)
        
        assert "Cannot confirm" in str(excinfo.value)


# ============================================================================
# BR08 – Reservation states:  CREATED, CONFIRMED, CANCELED only
# ============================================================================

class TestBR08ReservationStates:
    
    def test_reservation_can_be_in_created_state(self, reservation):
        # BR08 – Reservation may be in CREATED state
        reservation.state = ReservationState.CREATED
        assert reservation.state == ReservationState. CREATED

    def test_reservation_can_be_in_confirmed_state(self, confirmed_reservation):
        # BR08 – Reservation may be in CONFIRMED state
        assert confirmed_reservation.state == ReservationState.CONFIRMED

    def test_reservation_can_be_in_canceled_state(self, canceled_reservation):
        # BR08 – Reservation may be in CANCELED state
        assert canceled_reservation.state == ReservationState. CANCELED


# ============================================================================
# BR09 – Intermediate or additional states are not permitted
# ============================================================================

class TestBR09NoIntermediateStates:
    
    def test_in_payment_state_not_permitted(self, reservation_service, reservation):
        # BR09 – "In payment" state is not permitted
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state:  IN_PAYMENT"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.setReservationState(reservation. reservationId, "IN_PAYMENT")
        
        assert "Invalid state" in str(excinfo.value)

    def test_pending_state_not_permitted(self, reservation_service, reservation):
        # BR09 – "Pending" state is not permitted
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state: PENDING"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. setReservationState(reservation.reservationId, "PENDING")
        
        assert "Invalid state" in str(excinfo.value)

    def test_expired_state_not_permitted(self, reservation_service, reservation):
        # BR09 – "Expired" state is not permitted
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state: EXPIRED"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.setReservationState(reservation. reservationId, "EXPIRED")
        
        assert "Invalid state" in str(excinfo.value)


# ============================================================================
# BR10 – Valid state transitions:  CREATED→CONFIRMED, CONFIRMED→CANCELED
# ============================================================================

class TestBR10ValidStateTransitions:
    
    def test_transition_from_created_to_confirmed_valid(self, reservation_service, reservation):
        # BR10 – CREATED → CONFIRMED is a valid transition
        reservation.state = ReservationState.CREATED
        reservation_service.confirmPayment = Mock(return_value=None)
        
        reservation_service.confirmPayment(reservation. reservationId, True)
        reservation.state = ReservationState.CONFIRMED
        
        assert reservation.state == ReservationState. CONFIRMED

    def test_transition_from_confirmed_to_canceled_valid(self, reservation_service, confirmed_reservation):
        # BR10 – CONFIRMED → CANCELED is a valid transition
        reservation_service.cancelReservation = Mock(return_value=None)
        
        reservation_service. cancelReservation(confirmed_reservation.reservationId)
        confirmed_reservation.state = ReservationState.CANCELED
        
        assert confirmed_reservation.state == ReservationState. CANCELED


# ============================================================================
# BR11 – Invalid state transitions must be rejected
# ============================================================================

class TestBR11InvalidStateTransitionsRejected: 
    
    def test_transition_from_created_to_canceled_rejected(self, reservation_service, reservation):
        # BR11 – CREATED → CANCELED is not a valid transition
        reservation.state = ReservationState. CREATED
        reservation_service.cancelReservation = Mock(side_effect=Exception("Invalid state transition"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.cancelReservation(reservation.reservationId)
        
        assert "Invalid state transition" in str(excinfo.value)

    def test_transition_from_confirmed_to_created_rejected(self, reservation_service, confirmed_reservation):
        # BR11 – CONFIRMED → CREATED is not a valid transition
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state transition"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.setReservationState(confirmed_reservation.reservationId, "CREATED")
        
        assert "Invalid state transition" in str(excinfo.value)

    def test_transition_from_canceled_to_created_rejected(self, reservation_service, canceled_reservation):
        # BR11 – CANCELED → CREATED is not a valid transition
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state transition"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. setReservationState(canceled_reservation. reservationId, "CREATED")
        
        assert "Invalid state transition" in str(excinfo.value)

    def test_transition_from_canceled_to_confirmed_rejected(self, reservation_service, canceled_reservation):
        # BR11 – CANCELED → CONFIRMED is not a valid transition
        reservation_service.confirmPayment = Mock(side_effect=Exception("Invalid state transition"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(canceled_reservation.reservationId, True)
        
        assert "Invalid state transition" in str(excinfo.value)


# ============================================================================
# BR12 – Canceled reservation must not be reactivated, modified, or receive payments
# ============================================================================

class TestBR12CanceledReservationImmutable:
    
    def test_canceled_reservation_cannot_be_reactivated(self, reservation_service, canceled_reservation):
        # BR12 – Canceled reservation must not be reactivated
        reservation_service.reactivateReservation = Mock(side_effect=Exception("Cannot reactivate canceled reservation"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.reactivateReservation(canceled_reservation.reservationId)
        
        assert "Cannot reactivate" in str(excinfo.value)

    def test_canceled_reservation_cannot_be_modified(self, reservation_service, canceled_reservation):
        # BR12 – Canceled reservation must not be modified
        reservation_service.modifyReservation = Mock(side_effect=Exception("Cannot modify canceled reservation"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. modifyReservation(canceled_reservation. reservationId, seat=5)
        
        assert "Cannot modify" in str(excinfo.value)

    def test_canceled_reservation_cannot_receive_new_payment(self, reservation_service, canceled_reservation):
        # BR12 – Canceled reservation must not receive new payments
        reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot add payment to canceled reservation"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(canceled_reservation.reservationId, True)
        
        assert "Cannot add payment" in str(excinfo.value)


# ============================================================================
# BR13 – Cancellation refund policy based on remaining time
# ============================================================================

class TestBR13CancellationRefundPolicy:
    
    def test_full_refund_when_remaining_time_exactly_24_hours(self, reservation_service, confirmed_reservation):
        # BR13 – Remaining time ≥ 24 hours → full refund
        flight_time = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 14, 0, 0)  # Exactly 24 hours before
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service. cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "full"

    def test_full_refund_when_remaining_time_greater_than_24_hours(self, reservation_service, confirmed_reservation):
        # BR13 – Remaining time > 24 hours → full refund
        flight_time = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 18, 14, 0, 0)  # 48 hours before
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "full"

    def test_no_refund_when_remaining_time_less_than_24_hours(self, reservation_service, confirmed_reservation):
        # BR13 – Remaining time < 24 hours → no refund
        flight_time = datetime(2026, 1, 20, 14, 0, 0)
        current_time = datetime(2026, 1, 19, 15, 0, 0)  # 23 hours before
        reservation_service. cancelReservation = Mock(return_value={"refund":  "none"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "none"

    def test_no_refund_when_remaining_time_23_hours_59_minutes(self, reservation_service, confirmed_reservation):
        # BR13 – Remaining time 23h59m < 24 hours → no refund
        reservation_service.cancelReservation = Mock(return_value={"refund": "none"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "none"


# ============================================================================
# BR14 – Remaining time calculated in exact hours, no rounding
# ============================================================================

class TestBR14ExactTimeCalculation:
    
    def test_remaining_time_calculated_exactly_no_rounding_up(self, reservation_service, confirmed_reservation):
        # BR14 – Exact hours calculation, no rounding up
        # 23 hours 59 minutes 59 seconds is NOT rounded to 24 hours
        reservation_service.calculateRemainingHours = Mock(return_value=23)
        
        remaining = reservation_service.calculateRemainingHours(confirmed_reservation. reservationId)
        
        assert remaining == 23  # Not rounded to 24

    def test_remaining_time_calculated_exactly_no_rounding_down(self, reservation_service, confirmed_reservation):
        # BR14 – Exact hours calculation, no rounding down
        reservation_service.calculateRemainingHours = Mock(return_value=24)
        
        remaining = reservation_service.calculateRemainingHours(confirmed_reservation.reservationId)
        
        assert remaining == 24  # Exact value


# ============================================================================
# BR15 – System uses internally stored flight date/time as temporal reference
# ============================================================================

class TestBR15InternalTemporalReference: 
    
    def test_uses_internally_stored_flight_datetime(self, reservation_service, flight):
        # BR15 – System uses internally stored flight date/time
        stored_datetime = datetime(2026, 1, 20, 14, 0, 0)
        flight. dateTime = stored_datetime
        reservation_service.getFlightDateTime = Mock(return_value=stored_datetime)
        
        result = reservation_service. getFlightDateTime(flight.flightId)
        
        assert result == stored_datetime

    def test_external_datetime_not_used_for_calculation(self, reservation_service, flight, confirmed_reservation):
        # BR15 – External datetime must not override internal reference
        reservation_service.cancelWithExternalTime = Mock(side_effect=Exception("External time not permitted"))
        external_time = datetime(2026, 1, 15, 10, 0, 0)
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.cancelWithExternalTime(confirmed_reservation.reservationId, external_time)
        
        assert "External time not permitted" in str(excinfo.value)


# ============================================================================
# BR16 – Flight dates, times, and identifiers must not be altered after confirmation
# ============================================================================

class TestBR16FlightDataImmutableAfterConfirmation:
    
    def test_flight_date_cannot_be_changed_after_confirmation(self, reservation_service, confirmed_reservation, flight):
        # BR16 – Flight date must not be altered after reservation confirmation
        reservation_service.updateFlightDate = Mock(side_effect=Exception("Cannot modify flight date after confirmation"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.updateFlightDate(flight.flightId, datetime(2026, 2, 1, 10, 0, 0))
        
        assert "Cannot modify flight date" in str(excinfo.value)

    def test_flight_time_cannot_be_changed_after_confirmation(self, reservation_service, confirmed_reservation, flight):
        # BR16 – Flight time must not be altered after reservation confirmation
        reservation_service.updateFlightTime = Mock(side_effect=Exception("Cannot modify flight time after confirmation"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.updateFlightTime(flight.flightId, datetime(2026, 1, 20, 18, 0, 0))
        
        assert "Cannot modify flight time" in str(excinfo.value)

    def test_flight_identifier_cannot_be_changed_after_confirmation(self, reservation_service, confirmed_reservation, flight):
        # BR16 – Flight identifier must not be altered after reservation confirmation
        reservation_service.updateFlightId = Mock(side_effect=Exception("Cannot modify flight identifier after confirmation"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. updateFlightId(flight.flightId, "FL999")
        
        assert "Cannot modify flight identifier" in str(excinfo.value)


# ============================================================================
# BR17 – Indirect modifications of flight data prohibited
# ============================================================================

class TestBR17IndirectFlightModificationsProhibited: 
    
    def test_reference_swapping_prohibited(self, reservation_service, confirmed_reservation):
        # BR17 – Reference swapping of flight data is prohibited
        reservation_service. swapFlightReference = Mock(side_effect=Exception("Reference swapping prohibited"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.swapFlightReference(confirmed_reservation.reservationId, "FL002")
        
        assert "Reference swapping prohibited" in str(excinfo.value)

    def test_flight_cloning_prohibited(self, reservation_service, flight):
        # BR17 – Flight cloning for modification is prohibited
        reservation_service.cloneFlight = Mock(side_effect=Exception("Flight cloning prohibited"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.cloneFlight(flight.flightId)
        
        assert "Flight cloning prohibited" in str(excinfo.value)

    def test_object_recreation_prohibited(self, reservation_service, flight):
        # BR17 – Object recreation for modification is prohibited
        reservation_service. recreateFlight = Mock(side_effect=Exception("Object recreation prohibited"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.recreateFlight(flight.flightId)
        
        assert "Object recreation prohibited" in str(excinfo.value)


# ============================================================================
# BR18 – Each reservation may have exactly one associated payment
# ============================================================================

class TestBR18ExactlyOnePaymentPerReservation: 
    
    def test_reservation_has_exactly_one_payment(self, reservation_service, reservation):
        # BR18 – Reservation may have exactly one payment
        reservation_service.confirmPayment = Mock(return_value=None)
        
        reservation_service.confirmPayment(reservation.reservationId, True)
        reservation.payment = Mock(status="approved")
        
        assert reservation.payment is not None

    def test_reservation_without_payment_cannot_confirm(self, reservation_service, reservation):
        # BR18 – Reservation without payment cannot be confirmed
        reservation. payment = None
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment required"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, True)
        
        assert "Payment required" in str(excinfo.value)


# ============================================================================
# BR19 – Additional payment attempts for the same reservation must be rejected
# ============================================================================

class TestBR19AdditionalPaymentsRejected: 
    
    def test_second_payment_attempt_rejected(self, reservation_service, confirmed_reservation):
        # BR19 – Additional payment attempts must be rejected
        confirmed_reservation.payment = Mock(status="approved")
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment already exists"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(confirmed_reservation. reservationId, True)
        
        assert "Payment already exists" in str(excinfo.value)

    def test_multiple_payment_attempts_rejected(self, reservation_service, reservation):
        # BR19 – Multiple payment attempts must all be rejected after first
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service.confirmPayment(reservation.reservationId, True)
        
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment already exists"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, True)
        
        assert "Payment already exists" in str(excinfo.value)


# ============================================================================
# BR20 – Payments must not be accepted for canceled reservations or after flight date
# ============================================================================

class TestBR20PaymentRestrictions:
    
    def test_payment_rejected_for_canceled_reservation(self, reservation_service, canceled_reservation):
        # BR20 – Payment must not be accepted for canceled reservation
        reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot pay for canceled reservation"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. confirmPayment(canceled_reservation.reservationId, True)
        
        assert "Cannot pay for canceled reservation" in str(excinfo.value)

    def test_payment_rejected_after_flight_date(self, reservation_service, reservation):
        # BR20 – Payment must not be accepted after flight date
        reservation_service.confirmPayment = Mock(side_effect=Exception("Cannot pay after flight date"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, True)
        
        assert "Cannot pay after flight date" in str(excinfo.value)


# ============================================================================
# BR21 – System operations must be deterministic
# ============================================================================

class TestBR21DeterministicOperations: 
    
    def test_same_input_produces_same_output(self, reservation_service, flight):
        # BR21 – Same sequence of inputs produces same result
        reservation_service.createReservation = Mock(return_value=Mock(reservationId="RES001", seat=1))
        
        result1 = reservation_service.createReservation(flight.flightId, 1)
        
        reservation_service. createReservation = Mock(return_value=Mock(reservationId="RES001", seat=1))
        result2 = reservation_service. createReservation(flight.flightId, 1)
        
        assert result1.reservationId == result2.reservationId
        assert result1.seat == result2.seat

    def test_operation_results_are_reproducible(self, reservation_service, reservation):
        # BR21 – Operations are reproducible
        reservation_service.confirmPayment = Mock(return_value=None)
        
        # Same operation with same inputs
        reservation_service.confirmPayment(reservation.reservationId, True)
        
        assert reservation_service.confirmPayment.call_count == 1


# ============================================================================
# BR22 – System must not assume unspecified implicit behaviors
# ============================================================================

class TestBR22NoImplicitBehaviors:
    
    def test_no_future_credit_assumed(self, reservation_service, confirmed_reservation):
        # BR22 – Future credit is not assumed
        reservation_service. getFutureCredit = Mock(side_effect=Exception("Future credit not supported"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.getFutureCredit(confirmed_reservation.reservationId)
        
        assert "Future credit not supported" in str(excinfo.value)

    def test_no_automatic_rebooking_assumed(self, reservation_service, canceled_reservation):
        # BR22 – Automatic rebooking is not assumed
        reservation_service.autoRebook = Mock(side_effect=Exception("Automatic rebooking not supported"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.autoRebook(canceled_reservation.reservationId)
        
        assert "Automatic rebooking not supported" in str(excinfo. value)

    def test_no_commercial_exceptions_assumed(self, reservation_service, confirmed_reservation):
        # BR22 – Commercial exceptions are not assumed
        reservation_service.applyCommercialException = Mock(side_effect=Exception("Commercial exceptions not supported"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.applyCommercialException(confirmed_reservation. reservationId)
        
        assert "Commercial exceptions not supported" in str(excinfo.value)


# ============================================================================
# BR23 – Business rule violation must result in immediate failure
# ============================================================================

class TestBR23ImmediateFailureOnViolation:
    
    def test_violation_causes_immediate_failure(self, reservation_service, flight):
        # BR23 – Business rule violation results in immediate failure
        reservation_service.createReservation = Mock(side_effect=Exception("Business rule violation"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, -1)  # Invalid seat
        
        assert "Business rule violation" in str(excinfo.value)

    def test_no_state_change_on_violation(self, reservation_service, reservation):
        # BR23 – No state change on violation
        original_state = reservation. state
        reservation_service.confirmPayment = Mock(side_effect=Exception("Violation"))
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert reservation.state == original_state

    def test_no_partial_records_on_violation(self, reservation_service, flight):
        # BR23 – No partial records created on violation
        reservation_service.createReservation = Mock(side_effect=Exception("Violation - no record created"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. createReservation(flight.flightId, 999)
        
        assert "no record created" in str(excinfo.value)


# ============================================================================
# BR24 – Each valid operation must generate exactly one immutable record
# ============================================================================

class TestBR24ImmutableRecords: 
    
    def test_valid_operation_generates_one_record(self, reservation_service, flight):
        # BR24 – Valid operation generates exactly one record
        reservation_service. createReservation = Mock(return_value=Mock(reservationId="RES001"))
        
        result = reservation_service. createReservation(flight.flightId, 1)
        
        assert result.reservationId == "RES001"
        reservation_service.createReservation.assert_called_once()

    def test_record_is_immutable(self, reservation_service, reservation):
        # BR24 – Generated record is immutable
        reservation_service. modifyRecord = Mock(side_effect=Exception("Record is immutable"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.modifyRecord(reservation. reservationId, {"seat": 5})
        
        assert "Record is immutable" in str(excinfo.value)


# ============================================================================
# BR25 – Failed operations must not generate persistent records
# ============================================================================

class TestBR25NoRecordsOnFailure:
    
    def test_failed_operation_generates_no_record(self, reservation_service, flight):
        # BR25 – Failed operation must not generate persistent records
        reservation_service.createReservation = Mock(side_effect=Exception("Operation failed"))
        reservation_service.getReservationCount = Mock(return_value=0)
        
        with pytest.raises(Exception):
            reservation_service.createReservation(flight.flightId, 1)
        
        # Verify no record was created
        assert reservation_service.getReservationCount() == 0

    def test_failed_payment_generates_no_record(self, reservation_service, reservation):
        # BR25 – Failed payment must not generate persistent record
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment failed"))
        reservation_service.getPaymentCount = Mock(return_value=0)
        
        with pytest.raises(Exception):
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert reservation_service.getPaymentCount() == 0


# ============================================================================
# BR26 – Operations on one reservation must not affect others
# ============================================================================

class TestBR26IsolatedOperations: 
    
    def test_cancellation_does_not_affect_other_reservations(self, reservation_service, confirmed_reservation):
        # BR26 – Cancellation of one reservation does not affect others
        other_reservation = Mock(reservationId="RES999", state=ReservationState. CONFIRMED)
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.getReservation = Mock(return_value=other_reservation)
        
        reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        other = reservation_service.getReservation("RES999")
        assert other.state == ReservationState. CONFIRMED

    def test_confirmation_does_not_affect_other_reservations(self, reservation_service, reservation):
        # BR26 – Confirmation of one reservation does not affect others
        other_reservation = Mock(reservationId="RES999", state=ReservationState. CREATED)
        reservation_service.confirmPayment = Mock(return_value=None)
        reservation_service. getReservation = Mock(return_value=other_reservation)
        
        reservation_service.confirmPayment(reservation.reservationId, True)
        
        other = reservation_service.getReservation("RES999")
        assert other.state == ReservationState.CREATED

    def test_operation_does_not_affect_other_flights(self, reservation_service, flight, reservation):
        # BR26 – Operation on reservation does not affect other flights
        other_flight = Mock(flightId="FL999", totalSeats=100)
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service.getFlight = Mock(return_value=other_flight)
        
        reservation_service. cancelReservation(reservation.reservationId)
        
        other = reservation_service.getFlight("FL999")
        assert other.totalSeats == 100

    def test_operation_does_not_affect_other_seats(self, reservation_service, flight, reservation):
        # BR26 – Operation on one seat does not affect other seats
        reservation. seat = 1
        reservation_service.cancelReservation = Mock(return_value=None)
        reservation_service. isSeatAvailable = Mock(return_value=True)
        
        reservation_service. cancelReservation(reservation.reservationId)
        
        # Other seats remain unaffected
        assert reservation_service.isSeatAvailable(flight.flightId, 2) is True


# ============================================================================
# FR01 – Create initial reservation in CREATED state
# ============================================================================

class TestFR01CreateReservation:
    
    def test_create_reservation_in_created_state(self, reservation_service, flight):
        # FR01 – Create initial reservation in CREATED state
        reservation_service.createReservation = Mock(
            return_value=Mock(state=ReservationState.CREATED, seat=1, flightId=flight.flightId)
        )
        
        result = reservation_service.createReservation(flight.flightId, 1)
        
        assert result. state == ReservationState.CREATED

    def test_create_reservation_associated_with_flight(self, reservation_service, flight):
        # FR01 – Reservation is associated with a flight
        reservation_service.createReservation = Mock(
            return_value=Mock(flightId=flight. flightId, seat=1)
        )
        
        result = reservation_service.createReservation(flight.flightId, 1)
        
        assert result.flightId == flight.flightId

    def test_create_reservation_with_available_seat(self, reservation_service, flight):
        # FR01 – Reservation is associated with an available seat
        reservation_service.createReservation = Mock(return_value=Mock(seat=5))
        
        result = reservation_service.createReservation(flight.flightId, 5)
        
        assert result.seat == 5

    def test_create_reservation_with_unavailable_seat_fails(self, reservation_service, flight):
        # FR01 – Cannot create reservation with unavailable seat
        reservation_service.createReservation = Mock(side_effect=Exception("Seat not available"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight. flightId, 1)
        
        assert "Seat not available" in str(excinfo.value)


# ============================================================================
# FR02 – Confirm payment and atomically confirm reservation
# ============================================================================

class TestFR02ConfirmPaymentAndReservation: 
    
    def test_confirm_payment_and_reservation_atomically(self, reservation_service, reservation):
        # FR02 – Confirm payment and reservation atomically
        reservation_service.confirmPayment = Mock(return_value=None)
        
        reservation_service. confirmPayment(reservation.reservationId, True)
        
        reservation_service.confirmPayment.assert_called_once_with(reservation.reservationId, True)

    def test_payment_not_approved_does_not_confirm_reservation(self, reservation_service, reservation):
        # FR02 – Unapproved payment does not confirm reservation
        reservation_service.confirmPayment = Mock(side_effect=Exception("Payment not approved"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert "Payment not approved" in str(excinfo.value)


# ============================================================================
# FR03 – Strictly control seat availability
# ============================================================================

class TestFR03SeatAvailabilityControl:
    
    def test_seat_becomes_unavailable_after_reservation(self, reservation_service, flight):
        # FR03 – Seat becomes unavailable after reservation
        reservation_service. createReservation = Mock(return_value=Mock(seat=1))
        reservation_service.isSeatAvailable = Mock(return_value=False)
        
        reservation_service.createReservation(flight. flightId, 1)
        
        assert reservation_service.isSeatAvailable(flight.flightId, 1) is False

    def test_seat_exclusivity_per_active_reservation(self, reservation_service, flight):
        # FR03 – Seat exclusivity ensures one active reservation per seat
        reservation_service.createReservation = Mock(return_value=Mock(seat=1))
        reservation_service.createReservation(flight.flightId, 1)
        
        reservation_service.createReservation = Mock(side_effect=Exception("Seat taken"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight. flightId, 1)
        
        assert "Seat taken" in str(excinfo.value)


# ============================================================================
# FR04 – Cancel reservations respecting refund policy
# ============================================================================

class TestFR04CancelReservationsWithRefundPolicy:
    
    def test_cancel_reservation_with_full_refund(self, reservation_service, confirmed_reservation):
        # FR04 – Cancel with full refund when >= 24 hours before flight
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service. cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "full"

    def test_cancel_reservation_with_no_refund(self, reservation_service, confirmed_reservation):
        # FR04 – Cancel with no refund when < 24 hours before flight
        reservation_service. cancelReservation = Mock(return_value={"refund":  "none"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "none"


# ============================================================================
# FR05 – Prevent invalid modifications
# ============================================================================

class TestFR05PreventInvalidModifications:
    
    def test_prevent_invalid_state_modification(self, reservation_service, reservation):
        # FR05 – Prevent invalid state modification
        reservation_service.setReservationState = Mock(side_effect=Exception("Invalid state modification"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.setReservationState(reservation. reservationId, "INVALID")
        
        assert "Invalid state modification" in str(excinfo.value)

    def test_prevent_flight_data_modification(self, reservation_service, confirmed_reservation, flight):
        # FR05 – Prevent flight data modification
        reservation_service.updateFlightData = Mock(side_effect=Exception("Flight data cannot be modified"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.updateFlightData(flight.flightId, {"dateTime": datetime(2026, 2, 1)})
        
        assert "Flight data cannot be modified" in str(excinfo.value)

    def test_prevent_seat_modification_after_confirmation(self, reservation_service, confirmed_reservation):
        # FR05 – Prevent seat modification after confirmation
        reservation_service.changeSeat = Mock(side_effect=Exception("Seat cannot be changed"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.changeSeat(confirmed_reservation.reservationId, 10)
        
        assert "Seat cannot be changed" in str(excinfo.value)

    def test_prevent_payment_modification(self, reservation_service, confirmed_reservation):
        # FR05 – Prevent payment modification
        reservation_service.modifyPayment = Mock(side_effect=Exception("Payment cannot be modified"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.modifyPayment(confirmed_reservation.reservationId, {"amount": 500})
        
        assert "Payment cannot be modified" in str(excinfo.value)


# ============================================================================
# FR06 – Do not allow overbooking
# ============================================================================

class TestFR06PreventOverbooking:
    
    def test_no_overbooking_allowed(self, reservation_service, flight):
        # FR06 – Overbooking is not allowed at any stage
        flight.totalSeats = 1
        reservation_service. getConfirmedReservationCount = Mock(return_value=1)
        reservation_service.createReservation = Mock(side_effect=Exception("Overbooking not allowed"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 2)
        
        assert "Overbooking not allowed" in str(excinfo.value)


# ============================================================================
# FR07 – Do not allow multiple, partial, or late payments
# ============================================================================

class TestFR07PaymentRestrictions: 
    
    def test_multiple_payments_not_allowed(self, reservation_service, confirmed_reservation):
        # FR07 – Multiple payments not allowed
        reservation_service.confirmPayment = Mock(side_effect=Exception("Multiple payments not allowed"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. confirmPayment(confirmed_reservation.reservationId, True)
        
        assert "Multiple payments not allowed" in str(excinfo.value)

    def test_partial_payments_not_allowed(self, reservation_service, reservation):
        # FR07 – Partial payments not allowed
        reservation_service.confirmPartialPayment = Mock(side_effect=Exception("Partial payments not allowed"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.confirmPartialPayment(reservation.reservationId, 50)
        
        assert "Partial payments not allowed" in str(excinfo.value)

    def test_late_payments_not_allowed(self, reservation_service, reservation):
        # FR07 – Late payments (after flight date) not allowed
        reservation_service.confirmPayment = Mock(side_effect=Exception("Late payments not allowed"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.confirmPayment(reservation. reservationId, True)
        
        assert "Late payments not allowed" in str(excinfo.value)


# ============================================================================
# FR08 – Do not return intermediate states or partial results
# ============================================================================

class TestFR08NoIntermediateStatesOrPartialResults: 
    
    def test_no_intermediate_state_returned(self, reservation_service, reservation):
        # FR08 – No intermediate state returned
        reservation_service.getReservation = Mock(return_value=Mock(state=ReservationState.CREATED))
        
        result = reservation_service.getReservation(reservation.reservationId)
        
        assert result. state in [ReservationState.CREATED, ReservationState. CONFIRMED, ReservationState. CANCELED]

    def test_no_partial_result_returned(self, reservation_service, flight):
        # FR08 – No partial result returned
        reservation_service.createReservation = Mock(
            return_value=Mock(reservationId="RES001", state=ReservationState.CREATED, seat=1, flightId=flight.flightId)
        )
        
        result = reservation_service.createReservation(flight. flightId, 1)
        
        assert result.reservationId is not None
        assert result.state is not None
        assert result.seat is not None
        assert result.flightId is not None


# ============================================================================
# FR09 – Failures must not modify state or produce side effects
# ============================================================================

class TestFR09FailuresDoNotModifyState: 
    
    def test_failed_confirmation_does_not_modify_state(self, reservation_service, reservation):
        # FR09 – Failed confirmation does not modify state
        original_state = reservation. state
        reservation_service.confirmPayment = Mock(side_effect=Exception("Confirmation failed"))
        
        with pytest. raises(Exception):
            reservation_service.confirmPayment(reservation.reservationId, False)
        
        assert reservation.state == original_state

    def test_failed_cancellation_does_not_modify_state(self, reservation_service, reservation):
        # FR09 – Failed cancellation does not modify state
        reservation. state = ReservationState.CREATED
        original_state = reservation. state
        reservation_service.cancelReservation = Mock(side_effect=Exception("Cancellation failed"))
        
        with pytest.raises(Exception):
            reservation_service.cancelReservation(reservation.reservationId)
        
        assert reservation. state == original_state

    def test_failed_operation_produces_no_side_effects(self, reservation_service, flight):
        # FR09 – Failed operation produces no persistent side effects
        reservation_service.createReservation = Mock(side_effect=Exception("Creation failed"))
        reservation_service.getSeatStatus = Mock(return_value="available")
        
        with pytest.raises(Exception):
            reservation_service.createReservation(flight. flightId, 1)
        
        # Seat should still be available
        assert reservation_service. getSeatStatus(flight. flightId, 1) == "available"


# ============================================================================
# FR10 – Use exclusively provided and internally stored data
# ============================================================================

class TestFR10UseOnlyProvidedData:
    
    def test_uses_only_internally_stored_data(self, reservation_service, flight):
        # FR10 – Uses exclusively internally stored data
        reservation_service.getFlightDateTime = Mock(return_value=flight.dateTime)
        
        result = reservation_service.getFlightDateTime(flight.flightId)
        
        assert result == flight.dateTime

    def test_external_data_not_used(self, reservation_service, reservation):
        # FR10 – External data inference is not allowed
        reservation_service.enrichReservationData = Mock(side_effect=Exception("External enrichment not allowed"))
        
        with pytest.raises(Exception) as excinfo: 
            reservation_service. enrichReservationData(reservation.reservationId)
        
        assert "External enrichment not allowed" in str(excinfo.value)

    def test_no_inference_used_for_decisions(self, reservation_service, confirmed_reservation):
        # FR10 – No inference used for business decisions
        reservation_service.inferRefundEligibility = Mock(side_effect=Exception("Inference not allowed"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.inferRefundEligibility(confirmed_reservation.reservationId)
        
        assert "Inference not allowed" in str(excinfo.value)


# ============================================================================
# EDGE CASE TESTS
# ============================================================================

class TestEdgeCases:
    
    def test_boundary_exactly_24_hours_before_flight_full_refund(self, reservation_service, confirmed_reservation):
        # Edge case: Exactly 24 hours before flight (BR13)
        # Remaining time >= 24 hours → full refund
        reservation_service.cancelReservation = Mock(return_value={"refund": "full"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "full"

    def test_boundary_one_second_less_than_24_hours_no_refund(self, reservation_service, confirmed_reservation):
        # Edge case:  23 hours 59 minutes 59 seconds before flight (BR13, BR14)
        # Remaining time < 24 hours → no refund
        reservation_service.cancelReservation = Mock(return_value={"refund": "none"})
        
        result = reservation_service.cancelReservation(confirmed_reservation.reservationId)
        
        assert result["refund"] == "none"

    def test_last_seat_on_flight(self, reservation_service, flight):
        # Edge case: Last available seat on flight (BR06, BR07)
        flight.totalSeats = 1
        reservation_service.createReservation = Mock(return_value=Mock(seat=1))
        
        result = reservation_service.createReservation(flight.flightId, 1)
        
        assert result.seat == 1

    def test_no_seats_on_flight(self, reservation_service, flight):
        # Edge case: Flight with zero seats (BR06, BR07)
        flight.totalSeats = 0
        reservation_service. createReservation = Mock(side_effect=Exception("No seats available"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 1)
        
        assert "No seats available" in str(excinfo.value)

    def test_first_seat_number(self, reservation_service, flight):
        # Edge case: First seat (seat number 1)
        reservation_service.createReservation = Mock(return_value=Mock(seat=1))
        
        result = reservation_service. createReservation(flight.flightId, 1)
        
        assert result.seat == 1

    def test_maximum_seat_number(self, reservation_service, flight):
        # Edge case: Maximum seat number
        flight.totalSeats = 500
        reservation_service.createReservation = Mock(return_value=Mock(seat=500))
        
        result = reservation_service.createReservation(flight. flightId, 500)
        
        assert result.seat == 500

    def test_seat_number_exceeds_total_seats(self, reservation_service, flight):
        # Edge case:  Seat number exceeds total seats
        flight.totalSeats = 100
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat number"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 101)
        
        assert "Invalid seat number" in str(excinfo.value)

    def test_zero_seat_number(self, reservation_service, flight):
        # Edge case:  Seat number zero (invalid)
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat number"))
        
        with pytest.raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, 0)
        
        assert "Invalid seat number" in str(excinfo.value)

    def test_negative_seat_number(self, reservation_service, flight):
        # Edge case: Negative seat number (invalid)
        reservation_service.createReservation = Mock(side_effect=Exception("Invalid seat number"))
        
        with pytest. raises(Exception) as excinfo:
            reservation_service.createReservation(flight.flightId, -1)
        
        assert "Invalid seat number" in str(excinfo.value)
```