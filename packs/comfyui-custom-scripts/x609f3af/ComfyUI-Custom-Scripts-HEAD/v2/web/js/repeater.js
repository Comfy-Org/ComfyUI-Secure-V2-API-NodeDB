// Reuse and create modes now expand in the backend through the bounded graph
// broker, so the executor and cache see the work. No frontend prompt rewrite is
// needed. The legacy "multi" mode remains intentionally unavailable: it changed
// the number of physical sockets and silently rewired consumers while submitting
// a workflow whose saved topology said something else.

export {};
