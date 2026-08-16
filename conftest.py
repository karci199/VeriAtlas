"""Make the tests import the checkout they live in.

The virtualenv is installed editable and its `veriatlas.pth` points at one fixed path —
`C:\\veri\\src`, the main working copy. Every other worktree shares that virtualenv, so
`import veriatlas` in a test resolved to main's source no matter which branch the test
came from. A worktree could change a dataclass, watch its new test fail against the old
definition, and a *passing* run proved nothing about the branch at all.

The scripts never had this: they do `sys.path.insert(0, "src")` themselves and so read the
checkout they are run from. Only the tests were reading somebody else's code.

pytest imports the rootdir conftest before collecting anything, so putting `src` at the
front here fixes it for every test in every worktree, with nothing to remember.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))
