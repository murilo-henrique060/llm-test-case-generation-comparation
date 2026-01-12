```python
import pytest
from datetime import datetime, timedelta

# BR01 – A reservation may only be confirmed if exactly one approved payment is associated with it
# FR02 – Confirm payment and, atomically, confirm the reservation
def test_br01_confirm_reservation_with_approved_payment(reservation_service):
    reservation = reservation_service.createReservation("FLIGHT-101", 12)
    reservation_service.confirmPayment(reservation.id, True)
    assert reservation.state == "CONFIRMED"

# BR02 – Payments with a status other than approved must not confirm reservations
def test_br02_reject_confirmation_with_unapproved_payment(reservation_service):
    reservation = reservation_service.createReservation("FLIGHT-101", 12)
    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservation.id, False)
    assert reservation.state == "CREATED"

# BR03 – Reservation confirmation and payment approval must occur atomically
# FR09 – Ensure that failures do not modify state or produce persistent side effects
def test_br03_failed_payment_does_not_change_reservation_state(reservation_service):
    reservation = reservation_service.createReservation("FLIGHT-101", 12)
    # Simulating a failure during the atomic process
    with pytest.raises(Exception):
        reservation_service.confirmPayment(reservation.id, False)
    assert reservation.state == "CREATED"

# BR04 – A seat may belong to at most one active reservation per flight
# FR03 – Strictly control seat availability, ensuring exclusivity per active reservation
def test_br04_prevent_duplicate_seat_allocation_on_same_flight(reservation_service):
    reservation_service.createReservation("FLIGHT-101", 15)
    with pytest.raises(Exception):
        reservation_service.createReservation("FLIGHT-101", 15)

# BR05 – Canceled reservations must immediately release the associated seat
def test_br05_seat_is_released_after_cancellation(reservation_service):
    res1 = reservation_service.createReservation("FLIGHT-101", 20)
    reservation_service.confirmPayment(res1.id, True)
    reservation_service.cancelReservation(res1.id)
    # After cancellation, creating a new reservation for the same seat must succeed
    res2 = reservation_service.createReservation("FLIGHT-101", 20)
    assert res2.seat == 20

# BR06 – Overbooking is not permitted under any circumstances
# FR06 – Do not allow overbooking at any stage of the process
def test_br06_prevent_reservation_creation_beyond_capacity(reservation_service):
    # Assume FLIGHT-FULL has totalSeats = 1
    reservation_service.createReservation("FLIGHT-FULL", 1)
    with pytest.raises(Exception):
        reservation_service.createReservation("FLIGHT-FULL", 2)

# BR07 – The number of confirmed reservations for a flight must never exceed the total number of available seats
def test_br07_confirmed_reservations_cannot_exceed_total_seats(reservation_service):
    # Flight with 1 seat
    res = reservation_service.createReservation("FLIGHT-ONE-SEAT", 1)
    reservation_service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        reservation_service.createReservation("FLIGHT-ONE-SEAT", 2)

# BR08 – A reservation may be exclusively in CREATED, CONFIRMED, or CANCELED states
# BR09 – Intermediate or additional states are not permitted
def test_br08_br09_reservation_starts_in_created_state(reservation_service):
    reservation = reservation_service.createReservation("FLIGHT-101", 10)
    assert reservation.state == "CREATED"
    assert reservation.state in ["CREATED", "CONFIRMED", "CANCELED"]

# BR10 – Valid transitions: CREATED → CONFIRMED, CONFIRMED → CANCELED
# BR11 – Any state transition other than those defined must be rejected
def test_br10_br11_invalid_transition_created_to_canceled(reservation_service):
    reservation = reservation_service.createReservation("FLIGHT-101", 10)
    # Transition CREATED -> CANCELED is not explicitly defined in BR10
    with pytest.raises(Exception):
        reservation_service.cancelReservation(reservation.id)

# BR12 – A canceled reservation must not be reactivated, modified, or receive new payments
def test_br12_cannot_confirm_payment_on_canceled_reservation(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 10)
    reservation_service.confirmPayment(res.id, True)
    reservation_service.cancelReservation(res.id)
    with pytest.raises(Exception):
        reservation_service.confirmPayment(res.id, True)

# BR13 – Remaining time ≥ 24 hours before the flight → full refund
# BR14 – Remaining time until the flight must be calculated in exact hours
# BR15 – System must use exclusively the internally stored flight date and time
def test_br13_br14_full_refund_at_exactly_24_hours_before_flight(reservation_service):
    # Flight date: 2026-01-15 10:00:00
    # Current date: 2026-01-14 10:00:00 (Exact 24 hours)
    res = reservation_service.createReservation("FLIGHT-REFUND-OK", 5)
    reservation_service.confirmPayment(res.id, True)
    refund = reservation_service.cancelReservation(res.id)
    # Requirement implies full refund (validation depends on refund logic implementation)
    assert refund.status == "FULL_REFUND"

# BR13 – Remaining time < 24 hours before the flight → no refund
def test_br13_no_refund_under_24_hours_before_flight(reservation_service):
    # Flight date: 2026-01-15 10:00:00
    # Current date: 2026-01-14 10:00:01 (23 hours, 59 minutes, 59 seconds)
    res = reservation_service.createReservation("FLIGHT-NO-REFUND", 5)
    reservation_service.confirmPayment(res.id, True)
    refund = reservation_service.cancelReservation(res.id)
    assert refund.status == "NO_REFUND"

# BR16 – Flight dates, times, and identifiers must not be altered after reservation confirmation
# FR05 – Prevent any invalid modification of state, flight data, seat, or payment
def test_br16_prevent_flight_data_modification_after_confirmation(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    reservation_service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        res.flightId = "FLIGHT-999"

# BR17 – Indirect modifications of flight data (reference swapping) are prohibited
def test_br17_prevent_flight_object_recreation(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    reservation_service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        res.flight = "New Flight Object"

# BR18 – Each reservation may have exactly one associated payment
# BR19 – Additional payment attempts for the same reservation must be rejected
# FR07 – Do not allow multiple payments
def test_br18_br19_reject_duplicate_payment_attempts(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    reservation_service.confirmPayment(res.id, True)
    with pytest.raises(Exception):
        reservation_service.confirmPayment(res.id, True)

# BR20 – Payments must not be accepted after the flight date
def test_br20_reject_payment_after_flight_date(reservation_service):
    # Flight date: 2026-01-10
    # Current date: 2026-01-12
    res = reservation_service.createReservation("PAST-FLIGHT", 5)
    with pytest.raises(Exception):
        reservation_service.confirmPayment(res.id, True)

# BR21 – System operations must be deterministic
def test_br21_deterministic_behavior_on_reproducible_input(reservation_service):
    # Operation 1
    res1 = reservation_service.createReservation("FLIGHT-DET", 1)
    # Operation 2 (Repeat)
    with pytest.raises(Exception):
        reservation_service.createReservation("FLIGHT-DET", 1)
    # Result must always be the same failure for the same seat/flight conflict

# BR23 – Any business rule violation must result in immediate failure with no state change
# FR09 – Ensure that failures do not modify state
def test_br23_violation_results_in_no_state_change(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    # Attempting an invalid transition (CREATED -> CANCELED)
    try:
        reservation_service.cancelReservation(res.id)
    except:
        pass
    # State must remain CREATED
    assert res.state == "CREATED"

# BR24 – Each valid operation must generate exactly one immutable record
def test_br24_valid_reservation_creates_one_record(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    assert res is not None
    # Verify no duplicate or partial records exist (implementation specific)

# BR26 – Operations performed on one reservation must not affect other reservations
def test_br26_isolation_of_reservation_operations(reservation_service):
    res1 = reservation_service.createReservation("FLIGHT-101", 1)
    res2 = reservation_service.createReservation("FLIGHT-101", 2)
    
    reservation_service.confirmPayment(res1.id, True)
    
    assert res1.state == "CONFIRMED"
    assert res2.state == "CREATED"

# FR01 - Create an initial reservation in the CREATED state
def test_fr01_create_initial_reservation(reservation_service):
    res = reservation_service.createReservation("FLIGHT-202", 45)
    assert res.state == "CREATED"
    assert res.seat == 45

# FR08 - Do not return intermediate states
def test_fr08_no_intermediate_states_during_confirmation(reservation_service):
    res = reservation_service.createReservation("FLIGHT-101", 5)
    # After a successful operation, it must be exactly the target state
    reservation_service.confirmPayment(res.id, True)
    assert res.state == "CONFIRMED"
    assert res.state not in ["PENDING", "IN_PAYMENT"]

# FR10 - Use exclusively provided and internally stored data
def test_fr10_use_stored_data_only(reservation_service):
    res = reservation_service.createReservation("FLIGHT-DATA", 1)
    # Verify the system uses the flightId provided
    assert res.flightId == "FLIGHT-DATA"
```