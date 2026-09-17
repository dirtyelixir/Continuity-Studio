"""Keep historical fixture sources stable and external semantic calls explicit."""
import copy
import pytest
from studio import shot_state


@pytest.fixture(autouse=True)
def offline_canonical_boundary(request, monkeypatch):
    # Existing domain tests intentionally use pre-canonical Production fixtures
    # and exact legacy media hashes. They test their own boundary, not a live
    # creative provider. Dedicated marked tests exercise the real precommit
    # compiler/transaction path with an explicit deterministic provider double.
    if not request.node.get_closest_marker('canonical_state'):
        monkeypatch.setattr(shot_state,'prepare_plan',lambda plan,*args,**kwargs:copy.deepcopy(plan))
    def forbidden(*args,**kwargs):
        raise AssertionError('A test must explicitly supply its canonical semantic provider')
    monkeypatch.setattr(shot_state,'_call',forbidden)
