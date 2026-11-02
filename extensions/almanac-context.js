// Host-owned generation state. No live task/conversation state enters the vault.
export class ContextGeneration {
  constructor(instanceId) {
    this.instanceId = instanceId;
    this.epoch = 0;
    this.situation = "fresh";
  }
  compact() {
    this.epoch += 1;
    this.situation = "post_compaction";
  }
  request({ cwd, sessionId, prompt, maxChars }) {
    const epoch = this.epoch;
    return { epoch, args: ["session-context", "--cwd", cwd, "--session-id", sessionId,
      "--prompt", prompt, "--token-budget", String(Math.max(0, Math.floor(maxChars / 4))),
      "--situation", this.situation, "--host-instance-id", this.instanceId,
      "--context-epoch", String(epoch)] };
  }
  current(request) { return request.epoch === this.epoch; }
  returned(request) {
    if (!this.current(request)) return false;
    this.situation = "resume";
    return true;
  }
}
