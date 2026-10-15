"""Typed CPU embedding cache over the public string storage domain.

The original key is SHA256(prompt.strip()), deliberately without a model or
precision suffix. Only cache representation and owned storage IO change; no
pickle is read and no host cache path is exposed. SDK integration is pending.
"""
import base64
import hashlib
import json
import logging
import math

FORMAT='wan-text-embedding-cache-v1'
PART_BYTES=32*1024
MAX_BYTES=64*1024*1024
MAX_HEADER_CHARS=512*1024
MAX_TENSORS=64
log=logging.getLogger(__name__)


def prompt_key(prompt):
    if not isinstance(prompt,str):raise TypeError('Prompt cache keys require text')
    return hashlib.sha256(prompt.strip().encode('utf-8')).hexdigest()


class TextEmbeddingCache:
    def __init__(self,storage):
        self.storage=storage

    @staticmethod
    def _root(prompt):return 'wan-text-cache-'+prompt_key(prompt)

    async def exists(self,prompt):
        # Original code checks file existence even if loading its contents failed.
        return await self.storage.get(self._root(prompt)) is not None

    async def get(self,prompt):
        import torch
        try:
            encoded=await self.storage.get(self._root(prompt))
            if encoded is None:return None
            if not isinstance(encoded,str) or len(encoded)>MAX_HEADER_CHARS:raise ValueError('Cache header exceeds bounds')
            record=json.loads(encoded)
            if not isinstance(record,dict) or set(record)!={'format','prompt_sha256','tensors'}:
                raise ValueError('Invalid text cache header')
            if record['format']!=FORMAT or record['prompt_sha256']!=prompt_key(prompt):raise ValueError('Wrong text cache identity')
            entries=record['tensors']
            if not isinstance(entries,list) or len(entries)>MAX_TENSORS:raise ValueError('Too many cached embeddings')
            types={'float16':torch.float16,'bfloat16':torch.bfloat16,'float32':torch.float32,'float64':torch.float64}
            checked=[];total=0
            for entry in entries:
                if not isinstance(entry,dict) or set(entry)!={'dtype','shape','bytes','sha256','parts'}:
                    raise ValueError('Invalid cached tensor descriptor')
                kind=entry['dtype'];shape=entry['shape'];parts=entry['parts']
                if not isinstance(kind,str) or kind not in types:raise ValueError('Unsupported cached embedding dtype')
                if not isinstance(shape,list) or len(shape)>4 or any(type(n) is not int or not 0<=n<=16384 for n in shape):
                    raise ValueError('Invalid cached embedding dimensions')
                count=math.prod(shape)*torch.empty((),dtype=types[kind]).element_size()
                if type(entry['bytes']) is not int or count!=entry['bytes'] or count>MAX_BYTES:
                    raise ValueError('Cached embedding byte count exceeds bounds')
                total+=count
                if total>MAX_BYTES or not isinstance(parts,list) or len(parts)!=(count+PART_BYTES-1)//PART_BYTES:
                    raise ValueError('Text cache allocation exceeds bounds')
                if not isinstance(entry['sha256'],str) or len(entry['sha256'])!=64:raise ValueError('Invalid cache digest')
                checked.append((entry,types[kind]))
            values=[]
            for entry,dtype in checked:
                tensor=torch.empty(entry['shape'],dtype=dtype,device='cpu')
                destination=memoryview(tensor.reshape(-1).view(torch.uint8).numpy())
                hasher=hashlib.sha256();offset=0
                for index,part in enumerate(entry['parts']):
                    if not isinstance(part,dict) or set(part)!={'key','bytes','sha256'}:raise ValueError('Invalid cache part')
                    wanted=min(PART_BYTES,entry['bytes']-offset)
                    if type(part['bytes']) is not int or part['bytes']!=wanted:raise ValueError('Wrong cached part size')
                    expected_key=self._part_key(record['prompt_sha256'],entry['sha256'],index)
                    if part['key']!=expected_key:raise ValueError('Wrong cached part identity')
                    value=await self.storage.get(expected_key)
                    if not isinstance(value,str) or len(value)>4*((wanted+2)//3):raise ValueError('Invalid cache part encoding')
                    raw=base64.b64decode(value,validate=True)
                    if len(raw)!=wanted or hashlib.sha256(raw).hexdigest()!=part['sha256']:raise ValueError('Cached part changed')
                    destination[offset:offset+wanted]=raw;hasher.update(raw);offset+=wanted
                if hasher.hexdigest()!=entry['sha256']:raise ValueError('Cached tensor changed')
                values.append(tensor)
            return values
        except Exception as error:
            log.warning('Failed to load cached text embeddings; will re-encode: %s',error)
            return None

    @staticmethod
    def _part_key(prompt_digest,tensor_digest,index):
        value=FORMAT+'-'+prompt_digest+'-'+tensor_digest+'-'+str(index)
        return 'wan-text-part-'+hashlib.sha256(value.encode()).hexdigest()

    async def get_pair(self,positive_prompt,negative_prompt):
        return await self.get(positive_prompt),await self.get(negative_prompt)

    async def store_if_absent(self,prompt,values):
        import torch
        try:
            if await self.exists(prompt):return False
            if not isinstance(values,list) or len(values)>MAX_TENSORS:raise ValueError('Text cache requires the original tensor list')
            allowed={torch.float16,torch.bfloat16,torch.float32,torch.float64}
            total=0
            for value in values:
                if not isinstance(value,torch.Tensor) or value.device.type!='cpu' or value.layout!=torch.strided or value.dtype not in allowed:
                    raise ValueError('Text cache supports actual dense CPU floating tensors')
                if value.ndim>4 or any(n>16384 for n in value.shape):raise ValueError('Cached embedding shape exceeds bounds')
                total+=value.numel()*value.element_size()
                if total>MAX_BYTES:raise ValueError('Text cache exceeds its bounded allocation domain')
            entries=[];prompt_digest=prompt_key(prompt)
            for value in values:
                tensor=value.detach().contiguous();view=memoryview(tensor.reshape(-1).view(torch.uint8).numpy())
                digest=hashlib.sha256(view).hexdigest();parts=[]
                for index,offset in enumerate(range(0,len(view),PART_BYTES)):
                    raw=view[offset:offset+PART_BYTES];key=self._part_key(prompt_digest,digest,index)
                    await self.storage.set(key,base64.b64encode(raw).decode('ascii'))
                    parts.append({'key':key,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()})
                entries.append({'dtype':str(tensor.dtype).removeprefix('torch.'),'shape':list(tensor.shape),
                    'bytes':len(view),'sha256':digest,'parts':parts})
            record={'format':FORMAT,'prompt_sha256':prompt_digest,'tensors':entries}
            encoded=json.dumps(record,separators=(',',':'),sort_keys=True)
            if len(encoded)>MAX_HEADER_CHARS:raise ValueError('Text cache header exceeds bounds')
            await self.storage.set(self._root(prompt),encoded)
            return True
        except Exception as error:
            log.warning('Failed to save text embeddings cache: %s',error)
            return False
