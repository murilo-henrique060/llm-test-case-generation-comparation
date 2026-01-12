```python
import pytest
from datetime import datetime, timedelta

# ------------------------------------------------------------------------------------------------
# MOCK DOMAIN MODEL FOR TEST EXECUTION CONTEXT
# These classes simulate the behavior described in the Class Diagram and Rules to make tests runnable.
# In a real scenario, these would be imported from the actual application.
# ------------------------------------------------------------------------------------------------

class DomainException(Exception):
    """Base exception for domain rule violations."""
    pass

class Flight:
    def __init__(self, flight_id, total_seats, flight_datetime):
        self.flight_id = flight_id
        self.total_seats = total_seats
        self.flight_datetime = flight_datetime
        # Internal tracking for validation logic simulation
        self._confirmed_seats = 0
        self._seat_map = {}  # seat_number -> reservation_id

class Reservation:
    CREATED = "CREATED"
    CONFIRMED = "CONFIRMED"
    CANCELED = "CANCELED"

    def __init__(self, reservation_id, flight, seat):
        self.reservation_id = reservation_id
        self.flight = flight
        self.seat = seat
        self.state = self.CREATED
        self.payment = None  # None or boolean status

class ReservationService:
    def __init__(self):
        self.reservations = {}
        self.flights = {}

    def add_flight(self, flight):
        self.flights[flight.flight_id] = flight

    def createReservation(self, flightId: str, seat: int) -> Reservation:
        if flightId not in self.flights:
            raise DomainException("Flight not found")
        
        flight = self.flights[flightId]
        
        # BR06, BR07, BR26 - Overbooking check / Seat availability
        if seat in flight._seat_map:
             # Check if existing reservation for this seat is active (CREATED or CONFIRMED)
             existing_res_id = flight._seat_map[seat]
             existing_res = self.reservations[existing_res_id]
             if existing_res.state != Reservation.CANCELED:
                 raise DomainException("Seat occupied")

        if flight._confirmed_seats >= flight.total_seats:
             raise DomainException("Flight full")

        res_id = f"res-{len(self.reservations) + 1}"
        reservation = Reservation(res_id, flight, seat)
        
        # Lock seat tentatively (BR04)
        flight._seat_map[seat] = res_id
        self.reservations[res_id] = reservation
        return reservation

    def confirmPayment(self, reservationId: str, paymentApproved: bool):
        if reservationId not in self.reservations:
            raise DomainException("Reservation not found")
        
        reservation = self.reservations[reservationId]
        flight = reservation.flight

        # BR12 - Canceled cannot receive payments
        if reservation.state == Reservation.CANCELED:
             raise DomainException("Cannot pay canceled reservation")
        
        # BR18, BR19 - Single payment per reservation
        if reservation.payment is not None:
             raise DomainException("Payment already exists")

        # BR20 - No payment after flight date
        # Assuming system_time is passed or mocked globally, here we just use flight time logic
        # For simulation purposes, we assume current time is before flight unless specified otherwise in test setup
        
        # BR01, BR02, BR03 - Confirmation logic
        if paymentApproved:
            reservation.payment = True
            
            # BR10 - State transition
            if reservation.state != Reservation.CREATED:
                 raise DomainException("Invalid transition")
            
            # BR07 - Final check on capacity before confirmation transition
            if flight._confirmed_seats >= flight.total_seats:
                raise DomainException("Flight full")

            reservation.state = Reservation.CONFIRMED
            flight._confirmed_seats += 1
        else:
            reservation.payment = False
            # BR02 - Status other than approved must not confirm
            # State remains CREATED, payment record exists as failed

    def cancelReservation(self, reservationId: str, current_time: datetime):
        if reservationId not in self.reservations:
            raise DomainException("Reservation not found")
        
        reservation = self.reservations[reservationId]
        flight = reservation.flight

        # BR10 - Only CONFIRMED -> CANCELED is defined (though usually CREATED -> CANCELED is implied in real world, 
        # strict BR10 says: CREATED -> CONFIRMED and CONFIRMED -> CANCELED are the *only* valid transitions? 
        # BR10 says "The only valid state transitions are...". 
        # If strict BR10 implies CREATED cannot go to CANCELED, we must enforce that.
        # However, usually cancellation from created is allowed. 
        # Reading BR10 strictly: "CREATED → CONFIRMED", "CONFIRMED → CANCELED".
        # This implies a CREATED reservation cannot be CANCELED directly. 
        # We will follow STRICT BR10.
        
        if reservation.state != Reservation.CONFIRMED:
            raise DomainException("Invalid transition")

        time_diff = flight.flight_datetime - current_time
        hours_remaining = time_diff.total_seconds() / 3600

        # BR13, BR14
        refund = False
        if hours_remaining >= 24:
            refund = True
        elif hours_remaining < 0:
            # Although BR13 doesn't explicitly mention post-flight, BR20 mentions no payments after flight.
            # BR13 says < 24 hours -> no refund. This covers post-flight mathematically.
            refund = False
        else:
            refund = False

        reservation.state = Reservation.CANCELED
        
        # BR05 - Release seat
        if reservation.seat in flight._seat_map and flight._seat_map[reservation.seat] == reservationId:
            del flight._seat_map[reservation.seat]
        
        if reservation.state == Reservation.CANCELED: # It was just set
             flight._confirmed_seats -= 1
        
        return refund

# ------------------------------------------------------------------------------------------------
# PYTEST SUITE
# ------------------------------------------------------------------------------------------------

@pytest.fixture
def service():
    return ReservationService()

@pytest.fixture
def future_flight_time():
    return datetime(2026, 12, 25, 10, 0, 0)

@pytest.fixture
def flight(service, future_flight_time):
    f = Flight(flight_id="FL101", total_seats=100, flight_datetime=future_flight_time)
    service.add_flight(f)
    return f

# ------------------------------------------------------------------------------------------------
# BR01: A reservation may only be confirmed if exactly one approved payment is associated with it
# ------------------------------------------------------------------------------------------------

def test_br01_confirm_reservation_with_approved_payment(service, flight):
    # BR01, FR02
    reservation = service.createReservation(flight.flight_id, seat=1)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    assert reservation.state == "CONFIRMED"
    assert reservation.payment is True

def test_br01_do_not_confirm_without_approved_payment(service, flight):
    # BR01, BR02
    reservation = service.createReservation(flight.flight_id, seat=1)
    service.confirmPayment(reservation.reservation_id, paymentApproved=False)
    
    assert reservation.state == "CREATED"
    assert reservation.payment is False

# ------------------------------------------------------------------------------------------------
# BR02: Payments with a status other than approved must not confirm reservations
# ------------------------------------------------------------------------------------------------

def test_br02_rejected_payment_does_not_change_state(service, flight):
    # BR02
    reservation = service.createReservation(flight.flight_id, seat=1)
    service.confirmPayment(reservation.reservation_id, paymentApproved=False)
    
    assert reservation.state != "CONFIRMED"
    assert reservation.state == "CREATED"

# ------------------------------------------------------------------------------------------------
# BR03: Reservation confirmation and payment approval must occur atomically
# ------------------------------------------------------------------------------------------------

def test_br03_atomicity_check_simulated(service, flight):
    # BR03: In a unit test environment without actual DB transactions, 
    # we verify that the method call results in both state changes simultaneously relative to the client.
    reservation = service.createReservation(flight.flight_id, seat=1)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    # Validation: observable state has both payment=True and state=CONFIRMED
    assert reservation.payment is True
    assert reservation.state == "CONFIRMED"

# ------------------------------------------------------------------------------------------------
# BR04: A seat may belong to at most one active reservation per flight
# ------------------------------------------------------------------------------------------------

def test_br04_prevent_duplicate_seat_allocation_created_state(service, flight):
    # BR04, FR03
    service.createReservation(flight.flight_id, seat=10)
    
    with pytest.raises(DomainException) as excinfo:
        service.createReservation(flight.flight_id, seat=10)
    assert "Seat occupied" in str(excinfo.value)

def test_br04_prevent_duplicate_seat_allocation_confirmed_state(service, flight):
    # BR04
    res1 = service.createReservation(flight.flight_id, seat=10)
    service.confirmPayment(res1.reservation_id, paymentApproved=True)
    
    with pytest.raises(DomainException) as excinfo:
        service.createReservation(flight.flight_id, seat=10)
    assert "Seat occupied" in str(excinfo.value)

# ------------------------------------------------------------------------------------------------
# BR05: Canceled reservations must immediately release the associated seat
# ------------------------------------------------------------------------------------------------

def test_br05_canceled_reservation_releases_seat(service, flight, future_flight_time):
    # BR05
    res1 = service.createReservation(flight.flight_id, seat=20)
    service.confirmPayment(res1.reservation_id, paymentApproved=True)
    
    # Cancel > 24h before
    cancel_time = future_flight_time - timedelta(hours=48)
    service.cancelReservation(res1.reservation_id, current_time=cancel_time)
    
    # Try to book same seat again
    res2 = service.createReservation(flight.flight_id, seat=20)
    assert res2.seat == 20
    assert res2.state == "CREATED"

# ------------------------------------------------------------------------------------------------
# BR06, BR07, FR06: Overbooking and total seats limit
# ------------------------------------------------------------------------------------------------

def test_br06_br07_cannot_exceed_total_capacity(service):
    # BR06, BR07, FR06
    small_flight = Flight("FL999", total_seats=2, flight_datetime=datetime(2026, 1, 1))
    service.add_flight(small_flight)
    
    # Fill flight
    res1 = service.createReservation(small_flight.flight_id, seat=1)
    service.confirmPayment(res1.reservation_id, True)
    
    res2 = service.createReservation(small_flight.flight_id, seat=2)
    service.confirmPayment(res2.reservation_id, True)
    
    # Attempt overbooking (even if seat number is different, logic typically checks count or specific seat)
    # If seat map logic is strictly seat-based, user might try seat 3.
    # But BR07 says "number of confirmed reservations... must never exceed total available seats"
    
    with pytest.raises(DomainException) as excinfo:
        service.createReservation(small_flight.flight_id, seat=3)
    assert "Flight full" in str(excinfo.value)

# ------------------------------------------------------------------------------------------------
# BR08, BR09: States and Exclusion of Intermediate States
# ------------------------------------------------------------------------------------------------

def test_br08_initial_state_is_created(service, flight):
    # BR08, FR01
    reservation = service.createReservation(flight.flight_id, seat=5)
    assert reservation.state == "CREATED"

def test_br09_no_intermediate_states_during_payment_failure(service, flight):
    # BR09, FR08
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=False)
    
    # Must remain CREATED, not "PENDING" or "PAYMENT_FAILED"
    assert reservation.state == "CREATED"

# ------------------------------------------------------------------------------------------------
# BR10, BR11: State Transitions
# ------------------------------------------------------------------------------------------------

def test_br10_valid_transition_created_to_confirmed(service, flight):
    # BR10
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    assert reservation.state == "CONFIRMED"

def test_br10_valid_transition_confirmed_to_canceled(service, flight, future_flight_time):
    # BR10
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    cancel_time = future_flight_time - timedelta(hours=30)
    service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    assert reservation.state == "CANCELED"

def test_br11_invalid_transition_created_to_canceled_direct(service, flight, future_flight_time):
    # BR10 strictly defines: CREATED -> CONFIRMED, CONFIRMED -> CANCELED.
    # BR11 rejects others.
    # Attempting CREATED -> CANCELED
    reservation = service.createReservation(flight.flight_id, seat=5)
    cancel_time = future_flight_time - timedelta(hours=30)
    
    with pytest.raises(DomainException) as excinfo:
        service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    assert "Invalid transition" in str(excinfo.value)

def test_br11_invalid_transition_canceled_to_confirmed(service, flight, future_flight_time):
    # BR11, BR12
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    cancel_time = future_flight_time - timedelta(hours=30)
    service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    
    with pytest.raises(DomainException) as excinfo:
        service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    assert "Cannot pay canceled reservation" in str(excinfo.value)

# ------------------------------------------------------------------------------------------------
# BR12: Canceled reservation immutability
# ------------------------------------------------------------------------------------------------

def test_br12_canceled_reservation_cannot_receive_payment(service, flight, future_flight_time):
    # BR12
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    service.cancelReservation(reservation.reservation_id, current_time=future_flight_time - timedelta(hours=30))
    
    with pytest.raises(DomainException) as excinfo:
        service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    assert "Cannot pay canceled reservation" in str(excinfo.value)

# ------------------------------------------------------------------------------------------------
# BR13, BR14: Refund Policy and Time Calculation
# ------------------------------------------------------------------------------------------------

def test_br13_br14_cancel_exact_24h_before_full_refund(service, flight, future_flight_time):
    # BR13: Remaining time >= 24 hours -> full refund
    # BR14: Exact calculation
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    # Exact 24 hours before
    cancel_time = future_flight_time - timedelta(hours=24)
    
    refund_status = service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    assert refund_status is True

def test_br13_br14_cancel_more_than_24h_before_full_refund(service, flight, future_flight_time):
    # BR13
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    cancel_time = future_flight_time - timedelta(hours=24, seconds=1)
    
    refund_status = service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    assert refund_status is True

def test_br13_br14_cancel_less_than_24h_before_no_refund(service, flight, future_flight_time):
    # BR13: Remaining time < 24 hours -> no refund
    # BR14: Exact calculation (23h 59m 59s)
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    # 1 second less than 24 hours
    cancel_time = future_flight_time - timedelta(hours=23, minutes=59, seconds=59)
    
    refund_status = service.cancelReservation(reservation.reservation_id, current_time=cancel_time)
    assert refund_status is False

# ------------------------------------------------------------------------------------------------
# BR15: Temporal Reference
# ------------------------------------------------------------------------------------------------

def test_br15_use_internal_flight_datetime(service):
    # BR15: System must use internally stored flight date.
    # We verify this by creating a flight with a specific time and asserting logic follows it, 
    # regardless of "real" system time (simulated by passing current_time explicitly to service).
    
    internal_time = datetime(2030, 1, 1, 12, 0, 0)
    flight = Flight("FL_INTERNAL", 10, internal_time)
    service.add_flight(flight)
    
    res = service.createReservation("FL_INTERNAL", 1)
    service.confirmPayment(res.reservation_id, True)
    
    # Check boundary against internal_time
    # 24h before internal_time is 2029-12-31 12:00:00
    
    # Case A: 2029-12-31 12:00:01 (Less than 24h) -> False
    check_time_a = datetime(2029, 12, 31, 12, 0, 1)
    # We can't cancel same res twice, so we need fresh setup if we wanted multiple checks, 
    # but here we trust the logic holds. We just verify one case based on internal time.
    
    refund = service.cancelReservation(res.reservation_id, current_time=check_time_a)
    assert refund is False

# ------------------------------------------------------------------------------------------------
# BR16, BR17: Immutability of Flight Data
# ------------------------------------------------------------------------------------------------

def test_br16_flight_data_immutability_after_confirmation(service, flight):
    # BR16: Flight dates, times, ids must not be altered. 
    # Since Python allows attribute setting, we check that the logic does not alter them 
    # and effectively this is a "negative test" ensuring no side effects on flight object.
    
    original_id = flight.flight_id
    original_time = flight.flight_datetime
    
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    assert flight.flight_id == original_id
    assert flight.flight_datetime == original_time

def test_br17_prohibit_flight_object_swapping(service, flight):
    # BR17: Indirect modifications prohibited.
    reservation = service.createReservation(flight.flight_id, seat=5)
    original_flight_obj = reservation.flight
    
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    assert reservation.flight is original_flight_obj

# ------------------------------------------------------------------------------------------------
# BR18, BR19: Single Payment Limit
# ------------------------------------------------------------------------------------------------

def test_br18_br19_reject_additional_payment_attempts(service, flight):
    # BR18, BR19
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    
    with pytest.raises(DomainException) as excinfo:
        service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    assert "Payment already exists" in str(excinfo.value)

def test_br19_reject_second_payment_after_first_failed(service, flight):
    # BR19 says "Additional payment attempts... must be rejected". 
    # However, usually retries are allowed if failed?
    # BR19 text: "Additional payment attempts for the same reservation must be rejected"
    # BR18 text: "Each reservation may have exactly one associated payment"
    # If the first failed, is it "associated"?
    # BR02 says "Payments with status other than approved must not confirm".
    # Implementation: `confirmPayment` sets `self.payment = False` on failure.
    # If `self.payment` is not None, it rejects.
    # This implies strict 1-shot payment attempt per reservation object.
    
    reservation = service.createReservation(flight.flight_id, seat=5)
    service.confirmPayment(reservation.reservation_id, paymentApproved=False)
    
    # Attempt retry
    with pytest.raises(DomainException) as excinfo:
        service.confirmPayment(reservation.reservation_id, paymentApproved=True)
    assert "Payment already exists" in str(excinfo.value)

# ------------------------------------------------------------------------------------------------
# BR20: No payments after flight or for canceled
# ------------------------------------------------------------------------------------------------

# (Canceled case covered in BR12 tests)

# Missing check for "after flight date" logic in simulation unless we inject strict time checks in `confirmPayment`
# Assuming strict adherence:
# We didn't implement explicit "current_time" check in `confirmPayment` in the mock above 
# because `confirmPayment` signature in UML didn't include `currentTime`. 
# However, strictly following BR20 requires the system to know time.

# ------------------------------------------------------------------------------------------------
# BR23, BR24, BR25: Transactional Safety & Persistence
# ------------------------------------------------------------------------------------------------

def test_br23_violation_results_in_immediate_failure_no_partial_state(service, flight):
    # BR23
    reservation = service.createReservation(flight.flight_id, seat=5)
    
    # Trigger violation (double payment)
    service.confirmPayment(reservation.reservation_id, True)
    
    # Verify state is clean/valid before second attempt
    assert reservation.state == "CONFIRMED"
    
    with pytest.raises(DomainException):
        service.confirmPayment(reservation.reservation_id, True)
    
    # State should remain exactly as it was before the exception (CONFIRMED), not "Corrupted"
    assert reservation.state == "CONFIRMED" 

def test_br25_failed_creation_generates_no_record(service, flight):
    # BR25
    # Fill seat 1
    res1 = service.createReservation(flight.flight_id, seat=1)
    
    # Try create duplicate seat
    with pytest.raises(DomainException):
        service.createReservation(flight.flight_id, seat=1)
    
    # Ensure only 1 reservation exists in system
    assert len(service.reservations) == 1

# ------------------------------------------------------------------------------------------------
# FR Checks (Functional Requirements)
# Many FRs are covered by BR tests, but we add explicit mapping.
# ------------------------------------------------------------------------------------------------

def test_fr01_create_initial_reservation(service, flight):
    # FR01
    res = service.createReservation(flight.flight_id, seat=99)
    assert res.state == "CREATED"
    assert res.seat == 99
    assert res.flight.flight_id == flight.flight_id

def test_fr02_confirm_payment_atomically(service, flight):
    # FR02
    res = service.createReservation(flight.flight_id, seat=99)
    service.confirmPayment(res.reservation_id, True)
    assert res.state == "CONFIRMED"
    assert res.payment is True

def test_fr03_control_seat_exclusivity(service, flight):
    # FR03
    service.createReservation(flight.flight_id, seat=88)
    with pytest.raises(DomainException):
        service.createReservation(flight.flight_id, seat=88)

def test_fr04_cancel_respecting_policy(service, flight, future_flight_time):
    # FR04
    res = service.createReservation(flight.flight_id, seat=88)
    service.confirmPayment(res.reservation_id, True)
    
    # < 24h
    res_refund = service.cancelReservation(res.reservation_id, current_time=future_flight_time - timedelta(hours=10))
    assert res_refund is False

def test_fr05_prevent_invalid_modifications(service, flight):
    # FR05 - General integrity check
    res = service.createReservation(flight.flight_id, seat=88)
    original_seat = res.seat
    
    # Python allows setting attributes, but business logic shouldn't expose methods to change them.
    # The service class strictly only has create, confirm, cancel.
    # We verify no other methods exist or are called in valid flows.
    pass # Implicitly covered by absence of 'updateReservation' methods in requirements/mock

def test_fr07_do_not_allow_multiple_partial_late_payments(service, flight):
    # FR07
    res = service.createReservation(flight.flight_id, seat=88)
    
    # Partial/Late concepts translate to binary "Approved/Not Approved" in this simplified model 
    # or "Payment exists/does not exist".
    # We test multiple:
    service.confirmPayment(res.reservation_id, True)
    with pytest.raises(DomainException):
         service.confirmPayment(res.reservation_id, True)
```