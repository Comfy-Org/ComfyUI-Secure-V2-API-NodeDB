# ComfyUI Cache Cleaner — Secure Nodes V2

This conversion preserves the Cache Cleaner node and its optional passthrough
inputs. Cache cleanup is performed by the permissioned host memory broker;
the pack no longer makes an unrestricted loopback HTTP request.

The deployment asks for consent to `models.manage`. The node does not receive
the model registry, server address, filesystem, network, or process authority.
