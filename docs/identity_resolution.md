# Identity Resolution (Draft)

## Core Rule (current)
Two records represent the same real person only when both first name and last name match after normalization.

## Notes
- Name matching is a strong signal, not an automatic merge trigger.
- Ambiguity requires human confirmation via an Identity Review UI.

## TODO
- Define canonical model (`Person`, `PersonLink`) and verification states.

