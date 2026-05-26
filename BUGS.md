# Regression Log

Every production bug that matters should end up here and in a permanent automated test.

## Active regression cases already covered

1. `random` name shadowing must never break text selection again.
   Test: `tests/test_thx_for_message.py::ThxForMessageTests::test_random_modules_are_not_shadowed`

2. Missing or broken dialogue keys in `texts.json` must be caught before release.
   Test: `tests/test_dialogue_texts.py`

3. The acknowledgement flow for user submissions must keep routing the right response type.
   Test: `tests/test_submission_acknowledgement.py`

## Rule for new bugs

1. Reproduce the bug in a failing test first.
2. Fix the code in a separate task.
3. Keep the regression test forever unless the feature is removed.
