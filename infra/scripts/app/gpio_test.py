import time

import RPi.GPIO as GPIO

# BCM numbering (GPIO numbers, not physical pins)
TEST_PINS = [2, 3, 4, 17, 18, 22, 23, 24, 25, 27, 5, 6, 12, 13, 16, 19, 20, 21, 26]


def test_input(pin):
    """Test pin as input with pull-up."""
    GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_UP)
    val = GPIO.input(pin)
    return val  # Expect HIGH (1) when floating


def test_output(pin):
    """Test pin as output toggle and measure with multimeter if needed."""
    GPIO.setup(pin, GPIO.OUT)
    results = []
    for state in [GPIO.HIGH, GPIO.LOW]:
        GPIO.output(pin, state)
        time.sleep(0.2)
        results.append(state)
    return results


def main():
    GPIO.setmode(GPIO.BCM)
    report = {}

    try:
        for pin in TEST_PINS:
            print(f"\nTesting GPIO{pin}...")

            # Input check
            val = test_input(pin)
            print(f"  Input mode with pull-up reads: {val} (expected 1)")

            # Output check
            states = test_output(pin)
            print(f"  Output mode toggled: {[int(s) for s in states]} (expect [1, 0])")

            report[pin] = {"input": val, "output": states}

        print("\n--- Test Complete ---")
        for pin, res in report.items():
            if res["input"] == 0:
                print("\n------ Broken ------")
            print(f"GPIO{pin}: input={res['input']} output={res['output']}")

    finally:
        GPIO.cleanup()


if __name__ == "__main__":
    main()
