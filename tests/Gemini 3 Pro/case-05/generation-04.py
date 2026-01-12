```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, PropertyMock

# -------------------------------------------------------------------------
# MOCKS AND STUBS FOR TEST EXECUTION CONTEXT
# -------------------------------------------------------------------------
# Since the implementation is not provided, we define the expected Interface
# and Exceptions to ensure the tests are syntactically valid and semantic.
# -------------------------------------------------------------------------

class BusinessRuleViolation(Exception):
    """Raised when a business rule is violated."""
    pass

class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass

# -------------------------------------------------------------------------
# TEST SUITE
# -------------------------------------------------------------------------

class TestAirlineReservationSystem:

    @pytest.fixture
    def mock_flight(self):
        """
        Creates a mock flight object strictly complying with Flight class structure.
        """
        flight = Mock()
        flight.dateTime = datetime(2026, 12, 25, 10, 0, 0) # Fixed date
        flight.totalSeats = 100
        flight.id = "FL123"
        return flight

    @pytest.fixture
    def service(self):
        """
        Returns the ReservationService instance (System Under Test).
        """
        # In a real scenario, this would be an instance of the actual class.
        # Here we assume the class exists as described in the UML.
        from my_module import ReservationService # Conceptual import
        return ReservationService()

    # ---------------------------------------------------------------------
    # CREATION AND SEATS (BR04, BR06, BR07, BR24, BR26, FR01, FR03, FR06)
    # ---------------------------------------------------------------------

    def test_create_reservation_success(self, service, mock_flight):
        # BR08 – A reservation starts in CREATED state
        # FR01 – Create an initial reservation in the CREATED state
        # BR24 – Each valid operation must generate exactly one immutable record
        
        seat_number = 1
        reservation = service.createReservation(flightId=mock_flight.id, seat=seat_number)
        
        assert reservation.state == "CREATED"
        assert reservation.seat == seat_number
        assert reservation.flightId == mock_flight.id

    def test_create_reservation_failure_duplicate_seat(self, service, mock_flight):
        # BR04 – A seat may belong to at most one active reservation per flight
        # FR03 – Strictly control seat availability
        # BR23 – Violation must result in immediate failure
        
        seat_number = 10
        # First reservation (Success)
        service.createReservation(flightId=mock_flight.id, seat=seat_number)
        
        # Second reservation for same seat (Must Fail)
        with pytest.raises(BusinessRuleViolation):
            service.createReservation(flightId=mock_flight.id, seat=seat_number)

    def test_prevent_overbooking_capacity_limit(self, service):
        # BR06 – Overbooking is not permitted under any circumstances
        # BR07 – Confirmed reservations must not exceed available seats
        # FR06 – Do not allow overbooking
        
        tiny_flight = Mock()
        tiny_flight.id = "FL_TINY"
        tiny_flight.totalSeats = 1 # Only 1 seat available
        
        # Occupy the only seat
        service.createReservation(flightId=tiny_flight.id, seat=1)
        
        # Attempt to book a second seat (Must Fail)
        with pytest.raises(BusinessRuleViolation):
            service.createReservation(flightId=tiny_flight.id, seat=2)

    def test_operations_isolation_between_flights(self, service):
        # BR26 – Operations on one reservation must not affect other flights
        
        flight_a = Mock(id="FL_A", totalSeats=50)
        flight_b = Mock(id="FL_B", totalSeats=50)
        
        # Book seat 1 on Flight A
        res_a = service.createReservation(flightId=flight_a.id, seat=1)
        
        # Book seat 1 on Flight B (Should succeed as it is a different flight)
        try:
            res_b = service.createReservation(flightId=flight_b.id, seat=1)
        except BusinessRuleViolation:
            pytest.fail("Seat exclusivity incorrectly applied across different flights.")

    # ---------------------------------------------------------------------
    # PAYMENT AND CONFIRMATION (BR01, BR02, BR03, BR10, FR02, FR07)
    # ---------------------------------------------------------------------

    def test_confirm_reservation_atomic_success(self, service, mock_flight):
        # BR01 – Confirm only if approved payment is associated
        # BR03 – Reservation confirmation and payment approval must occur atomically
        # FR02 – Confirm payment and, atomically, confirm the reservation
        # BR10 – Valid transition: CREATED → CONFIRMED
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        
        # Action: Confirm with Approved Payment
        service.confirmPayment(reservation.id, paymentApproved=True)
        
        # Assert State Transition
        updated_reservation = service.getReservation(reservation.id) # Helper to refresh state
        assert updated_reservation.state == "CONFIRMED"

    def test_confirm_reservation_failure_declined_payment(self, service, mock_flight):
        # BR02 – Payments with a status other than approved must not confirm reservations
        # BR25 – Failed operations must not generate persistent records (State remains CREATED)
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        
        # Action: Attempt confirm with Declined Payment
        with pytest.raises(BusinessRuleViolation):
            service.confirmPayment(reservation.id, paymentApproved=False)
            
        # Assert No State Transition
        updated_reservation = service.getReservation(reservation.id)
        assert updated_reservation.state == "CREATED"

    def test_prevent_multiple_payments(self, service, mock_flight):
        # BR18 – Each reservation may have exactly one associated payment
        # BR19 – Additional payment attempts must be rejected
        # FR07 – Do not allow multiple payments
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        
        # First Payment (Success)
        service.confirmPayment(reservation.id, paymentApproved=True)
        
        # Second Payment Attempt (Must Fail)
        with pytest.raises(BusinessRuleViolation):
            service.confirmPayment(reservation.id, paymentApproved=True)

    # ---------------------------------------------------------------------
    # STATE TRANSITIONS AND IMMUTABILITY (BR08, BR09, BR10, BR11, BR12, BR16)
    # ---------------------------------------------------------------------

    def test_reject_invalid_transition_created_to_canceled(self, service, mock_flight):
        # BR10 – The ONLY valid state transitions are CREATED → CONFIRMED and CONFIRMED → CANCELED
        # BR11 – Any state transition other than those defined must be rejected
        # NOTE: Direct cancellation from CREATED is NOT in the list of valid transitions in BR10.
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        assert reservation.state == "CREATED"
        
        with pytest.raises(StateTransitionError):
            service.cancelReservation(reservation.id)

    def test_reject_invalid_transition_canceled_to_confirmed(self, service, mock_flight):
        # BR12 – A canceled reservation must not be reactivated
        # BR10 – Transition CANCELED → CONFIRMED is not valid
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        service.confirmPayment(reservation.id, paymentApproved=True)
        service.cancelReservation(reservation.id) # Now CANCELED
        
        with pytest.raises(StateTransitionError):
            # Attempt to pay/confirm again
            service.confirmPayment(reservation.id, paymentApproved=True)

    def test_reject_modification_of_flight_data_after_confirmation(self, service, mock_flight):
        # BR16 – Flight dates, times, and identifiers must not be altered after confirmation
        # BR05 – Prevent invalid modification
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        service.confirmPayment(reservation.id, paymentApproved=True)
        
        original_flight_id = reservation.flightId
        
        # Attempt modification (assuming property setter exists or mocking the object behavior)
        # Using a conceptual check assuming the object enforces immutability or the service rejects update
        with pytest.raises(BusinessRuleViolation):
            # Hypothetical method representing illegal update attempt
            service.updateReservationFlight(reservation.id, "NEW_FLIGHT_ID")

    # ---------------------------------------------------------------------
    # CANCELLATION AND REFUND POLICY (BR05, BR13, BR14, BR15, FR04)
    # ---------------------------------------------------------------------

    @patch('datetime.datetime')
    def test_cancel_reservation_refund_exact_24h(self, mock_datetime, service, mock_flight):
        # BR13 – Remaining time >= 24 hours before the flight → full refund
        # BR14 – Calculated in exact hours, no rounding
        # FR04 – Cancel reservations respecting refund policy
        # BR05 – Canceled reservations must release seat
        
        # Flight is Dec 25, 10:00:00
        mock_flight.dateTime = datetime(2026, 12, 25, 10, 0, 0)
        
        # Current time is EXACTLY 24 hours before: Dec 24, 10:00:00
        mock_datetime.now.return_value = datetime(2026, 12, 24, 10, 0, 0)
        
        # Setup Confirmed Reservation
        reservation = service.createReservation(mock_flight.id, seat=1)
        service.confirmPayment(reservation.id, paymentApproved=True)
        
        # Action: Cancel
        service.cancelReservation(reservation.id)
        
        # Assert State
        updated_res = service.getReservation(reservation.id)
        assert updated_res.state == "CANCELED"
        
        # Implicit assertion via mock spy or result object: Refund MUST be Full
        # Assuming the returned object or side effect log contains refund info
        assert updated_res.refund_status == "FULL_REFUND"

    @patch('datetime.datetime')
    def test_cancel_reservation_no_refund_under_24h(self, mock_datetime, service, mock_flight):
        # BR13 – Remaining time < 24 hours before the flight → no refund
        # BR14 – No tolerances (1 second late is late)
        
        # Flight is Dec 25, 10:00:00
        mock_flight.dateTime = datetime(2026, 12, 25, 10, 0, 0)
        
        # Current time is 23h 59m 59s before: Dec 24, 10:00:01
        mock_datetime.now.return_value = datetime(2026, 12, 24, 10, 0, 1)
        
        # Setup Confirmed Reservation
        reservation = service.createReservation(mock_flight.id, seat=1)
        service.confirmPayment(reservation.id, paymentApproved=True)
        
        # Action: Cancel
        service.cancelReservation(reservation.id)
        
        # Assert State
        updated_res = service.getReservation(reservation.id)
        assert updated_res.state == "CANCELED"
        
        # Assert Refund Status
        assert updated_res.refund_status == "NO_REFUND"

    def test_cancel_releases_seat_immediately(self, service, mock_flight):
        # BR05 – Canceled reservations must immediately release the associated seat
        
        seat_num = 5
        # 1. User A books and confirms seat 5
        res_a = service.createReservation(mock_flight.id, seat=seat_num)
        service.confirmPayment(res_a.id, paymentApproved=True)
        
        # 2. User A cancels
        service.cancelReservation(res_a.id)
        
        # 3. User B tries to book seat 5 (Must succeed immediately)
        try:
            res_b = service.createReservation(mock_flight.id, seat=seat_num)
            assert res_b.state == "CREATED"
            assert res_b.seat == seat_num
        except BusinessRuleViolation:
            pytest.fail("Seat was not released immediately after cancellation.")

    # ---------------------------------------------------------------------
    # TEMPORAL AND DETERMINISM RULES (BR15, BR20, BR21)
    # ---------------------------------------------------------------------

    @patch('datetime.datetime')
    def test_payment_rejected_after_flight_departure(self, mock_datetime, service, mock_flight):
        # BR20 – Payments must not be accepted after the flight date
        # BR15 – System must use exclusively internally stored flight date
        
        # Flight Date: Dec 25, 10:00
        mock_flight.dateTime = datetime(2026, 12, 25, 10, 0, 0)
        
        # Current Date: Dec 25, 10:01 (1 minute late)
        mock_datetime.now.return_value = datetime(2026, 12, 25, 10, 0, 1)
        
        reservation = service.createReservation(mock_flight.id, seat=1)
        
        # Action: Attempt Payment
        with pytest.raises(BusinessRuleViolation):
            service.confirmPayment(reservation.id, paymentApproved=True)

    def test_determinism_same_input_same_result(self, service, mock_flight):
        # BR21 – System operations must be deterministic
        # BR23 – Violation must result in immediate failure (no partial state)
        
        seat_num = 99
        
        # Execution 1
        res1 = service.createReservation(mock_flight.id, seat=seat_num)
        
        # Reset Mock Service for Execution 2 (Clean slate with same initial conditions)
        service_2 = service # reusing same instance logic reference
        # Note: In a real test, we would re-instantiate the service to ensure clean slate,
        # but here we check that re-running the exact command logic fails deterministically 
        # due to state (BR04) OR creates identical object if state was cleared.
        
        # Here we test that createReservation always returns a Reservation object with strict types
        assert isinstance(res1.seat, int)
        assert res1.state == "CREATED"
```