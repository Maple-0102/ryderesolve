"""Snapshot-bound port for the teammate's unmodified Advocate package and our ADC client."""
from copy import deepcopy
from .agents import AgentError
from .vertex import VertexJudge
from .evidence_boundaries import EVIDENCE_BOUNDARIES


class TeammateAdvocate:
    def __init__(self, model_client):
        try:
            from ryderesolve_advocate import AdvocateSystem, CallableProvider
        except ImportError:
            raise AgentError('ADVOCATE_PACKAGE_MISSING') from None
        self.model = model_client
        self.system = AdvocateSystem(CallableProvider(self._generate))
        self.mode = 'teammate_google_vertex' if isinstance(model_client, VertexJudge) else 'teammate_custom_provider'
        self.last_metadata = {}
        self._invoked = False

    def _generate(self, system, user):
        self._invoked = True
        # Advocate emits arguments, not a Judge ruling; use the shared low-level JSON transport.
        return self.model.generate(system + '\n\n' + EVIDENCE_BOUNDARIES, user, max_output_tokens=8192)

    def __call__(self, snapshot, side, round_name, opponent=None):
        self.last_metadata = {}; self._invoked = False
        if side not in ('rider', 'driver') or round_name not in ('opening', 'response'):
            raise AgentError('ADVOCATE_INVALID_ROLE_OR_ROUND')
        if round_name == 'opening' and opponent is not None:
            raise AgentError('ADVOCATE_OPENING_MUST_BE_INDEPENDENT')
        if round_name == 'response':
            if not isinstance(opponent, dict): raise AgentError('ADVOCATE_OPPONENT_REQUIRED')
            if opponent.get('snapshot_id') != snapshot['snapshot_id']:
                raise AgentError('ADVOCATE_OPPONENT_SNAPSHOT_MISMATCH')
        from ryderesolve_advocate.validation import ContractError
        try:
            output = self.system.run_advocate(deepcopy(snapshot['evidence_pack']), deepcopy(snapshot['audit']),
                                             side, deepcopy(opponent))
        except ContractError:
            raise AgentError('ADVOCATE_TEAM_CONTRACT_REJECTED') from None
        finally:
            if self._invoked: self.last_metadata = deepcopy(getattr(self.model, 'last_metadata', {}))
        if output.get('snapshot_id', snapshot['snapshot_id']) != snapshot['snapshot_id']:
            raise AgentError('ADVOCATE_MODEL_SNAPSHOT_MISMATCH')
        output['snapshot_id'] = snapshot['snapshot_id']
        output['round'] = round_name
        return output
