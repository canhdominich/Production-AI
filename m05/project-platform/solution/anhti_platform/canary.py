import hashlib

PROMPTS = {
    "v1": "You are the support assistant of Giao Hang Anh Ti. Answer in Vietnamese, briefly, and name the policy you used.",
    "v2": "You are the support assistant of Giao Hang Anh Ti. Answer in Vietnamese in at most three sentences. Name the policy "
          "you used and say what the customer should do next.",
}


def bucket(user_id, salt, buckets=100):
    return int(hashlib.sha256(f"{salt}:{user_id}".encode()).hexdigest()[:8], 16) % buckets


class CanaryRouter:
    def __init__(self, stable="v1", canary="v2", percent=0, salt="release-2026-11"):
        self.stable, self.canary, self.percent, self.salt = stable, canary, percent, salt

    def route(self, user_id):
        return self.canary if bucket(user_id, self.salt) < self.percent else self.stable

    def prompt_for(self, version):
        return PROMPTS[version]


class RollbackController:
    def __init__(self, router, margin=0.05, min_samples=30, strikes=2, promote_after=6):
        self.router, self.margin, self.min_samples = router, margin, min_samples
        self.strikes_needed, self.promote_after = strikes, promote_after
        self.scores = {router.stable: [], router.canary: []}
        self.state, self.strikes, self.good_checks = "running", 0, 0

    def observe(self, version, score):
        if self.state == "running" and version in self.scores:
            self.scores[version].append(score)

    def check(self):
        if self.state != "running":
            return self.state
        stable, canary = self.scores[self.router.stable], self.scores[self.router.canary]
        if len(canary) < self.min_samples or len(stable) < self.min_samples:
            return "collecting"
        gap = sum(stable) / len(stable) - sum(canary) / len(canary)
        self.scores = {self.router.stable: [], self.router.canary: []}
        if gap > self.margin:
            self.strikes += 1
            self.good_checks = 0
            if self.strikes >= self.strikes_needed:
                self.router.percent, self.state = 0, "rolled_back"
        else:
            self.strikes = 0
            self.good_checks += 1
            if self.good_checks >= self.promote_after:
                self.router.percent, self.state = 100, "promoted"
        return self.state
