import json
from patchmem.models import Patch,TextBlock,ToolUse
from patchmem.influence_diff import compute_diff
patch=Patch(anchor_uuid='message-1',block=TextBlock(text='Use the safe configuration.'),rationale='Fixture comparison')
before=[ToolUse(id='tool-1',name='Read',input={'path':'old.yaml'})]
after=[ToolUse(id='tool-1',name='Read',input={'path':'new.yaml'}),ToolUse(id='tool-2',name='Read',input={'path':'policy.yaml'})]
diff=compute_diff(patch,before,after)
print(json.dumps([d.model_dump(exclude_none=True) for d in diff.changed],indent=2))
