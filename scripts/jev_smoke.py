#!/usr/bin/env python3
"""Two real Jev calls on a made-up sentence: one choice and one yes/no.

Prints the decision, probability, model and milliseconds. Never prints the key. Exits 1 with Jev's safe sentence
if Jev cannot be reached or refuses the key.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uptime.jev import JevClient, JevUnavailable  # noqa: E402

SAMPLE = ("Made-up example. The provider will keep the hosted service available 99.9% of each calendar month. "
          "If monthly availability falls below that level, the customer may request a service credit of 10% of "
          "that month's fee within thirty days.")


def main() -> int:
    jev = JevClient()
    try:
        picked = jev.choice("Which kind of contract does this text come from?",
                            ["service_level_agreement", "office_lease", "employment_contract", "unrecognised"],
                            SAMPLE)
        print(f"choice: {picked['choice']}  probability={picked['probability']}  model={picked['model']}  "
              f"milliseconds={picked['milliseconds']}")
        answer = jev.yes_no("Does the text say the customer may request a service credit when availability "
                            "falls below 99.9%?", SAMPLE)
        print(f"yes_no: yes={answer['yes']}  probability={answer['probability']}  model={answer['model']}  "
              f"milliseconds={answer['milliseconds']}")
    except JevUnavailable as error:
        print(f"Jev unavailable: {error.sentence}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
