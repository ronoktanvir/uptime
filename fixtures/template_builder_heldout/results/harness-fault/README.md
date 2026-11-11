# A run that measured nothing

`20261111T011503Z.json` is the first run of the evaluation on the version 2 engine. Every form shows `FAILED` after
0.0 seconds with no Claude call. That was a fault in the evaluation script, not a result: its call counter did not
pass through the model the new engine now names per call, so each reader call raised a `TypeError` before reaching
Claude. The script was fixed and the evaluation run again. This file is kept so the record is complete.
