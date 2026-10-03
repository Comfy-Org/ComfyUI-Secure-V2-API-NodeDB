# Preview Image with Pause

This Secure Nodes V2 conversion pauses a workflow at an image batch and lets
the user choose **Continue** or **Cancel** directly on the node.

## Usage

1. Connect an `IMAGE` batch to **Preview Image with Pause**.
2. Queue the workflow.
3. Review every image in the mounted preview.
4. Choose **Continue** to pass the same image batch downstream, or **Cancel**
   to interrupt the current execution.

The host creates and serves temporary previews. The pack receives only managed
image identities and cannot read or write arbitrary server paths. Each paused
execution has an opaque, one-use response token, so simultaneous executions
cannot consume one another's decisions.

An unanswered interaction expires after nine minutes. Closing the node while
it is waiting sends a cancellation response for that node's pending requests.

## Security model

- no process-global status or polling loop;
- no custom HTTP routes;
- no direct filesystem, server, or model-management imports;
- no ambient browser DOM, global `fetch`, or monkey-patching of queue APIs;
- frontend responses use the host interaction broker's correlated request ID.

## License

MIT — see [LICENSE](LICENSE).
