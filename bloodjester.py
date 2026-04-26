# ============================================================================
# 🥷 BLOOD JESTER ELITE – Max Extraction Stealth Rug  🥷
# ============================================================================
import sys, subprocess, os

def install(pkg):
    subprocess.check_call([sys.executable, "-m", "pip", "install", pkg])

required = ["matplotlib"]
for pkg in required:
    try:
        __import__(pkg.replace("-", "_"))
    except ImportError:
        install(pkg)

import math, random, warnings
from typing import List, Tuple, Optional
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", message="Glyph.*missing from font")

# ---------------------------------------------------------------------------
# 🧬 CONFIGURATION – Elite Stealth Settings
# ---------------------------------------------------------------------------
STEPS = 600
MIGRATION_TARGET_SOL = 10            # pool size that triggers migration
SLOW_BLEED_START = 350              # longer safe period to build trust
BLEED_INTERVAL_BASE = 12            # average interval, heavily randomised
BLEED_PERCENT_MEAN = 0.03           # base removal (overridden by random)
DUMP_FRACTION_MIN = 0.5
DUMP_FRACTION_MAX = 1.0
FAKE_BUY_PROB = 0.6                 # 60% chance after each bleed
PRE_BLEED_PUMP_PROB = 0.3           # 30% chance of a pump candle before bleed
PUMP_MIN = 0.05                     # min SOL for a pre‑bleed pump
PUMP_MAX = 0.1                      # max SOL for a pre‑bleed pump
FAKE_BUY_MIN = 0.02
FAKE_BUY_MAX = 0.06

TOKEN_DECIMALS = 6
INITIAL_SUPPLY = 1_000_000_000 * (10**TOKEN_DECIMALS)

N_SNIPERS = 3
N_RETAIL = 30
N_MOMENTUM = 2
N_DEVS = 12                          # increased burner count
MIN_TRADE_TOKENS = 1

# ---------------------------------------------------------------------------
# 🎨 AGENTS & SENTIMENT (unchanged)
# ---------------------------------------------------------------------------
class SimWallet:
    __slots__ = ("sol", "tokens")
    def __init__(self, sol: float, tokens: int):
        self.sol = sol
        self.tokens = tokens

class Sentiment:
    def __init__(self):
        self.hype = 0.5; self.fear = 0.0; self.ath = 0.0
    def update(self, price, sell_frac, whale, rug):
        if price > self.ath: self.ath = price; self.hype += 0.1
        self.hype *= 0.98; self.fear *= 0.95
        self.hype -= 0.03 * whale
        if sell_frac > 0.4: self.fear += 0.1
        if rug: self.fear = 1.0; self.hype = 0.0
        self.hype = max(0.0, min(1.0, self.hype))
        self.fear = max(0.0, min(1.0, self.fear))
    def buy_prob(self): return (0.5 + self.hype * 0.5) * (1.0 - self.fear)
    def sell_intensity(self): return 0.1 + self.fear * 0.3

class Sniper:
    def __init__(self, w: SimWallet, aggression=0.3): self.wallet = w; self.aggression = aggression
    def decide(self, phase, step):
        if phase == "BONDING" and self.wallet.sol > 0.01:
            amt = max(0.001, self.wallet.sol * self.aggression)
            return [("buy", amt, self)]
        return []

class Retail:
    def __init__(self, w: SimWallet): self.wallet = w
    def decide(self, price, sent):
        if random.random() < sent.buy_prob():
            amt = random.uniform(0.1, min(1.0, self.wallet.sol * 0.1))
            if self.wallet.sol >= amt and amt > 0.001:
                return [("buy", amt, self)]
        elif self.wallet.tokens >= MIN_TRADE_TOKENS:
            tok = int(self.wallet.tokens * sent.sell_intensity())
            if tok >= MIN_TRADE_TOKENS:
                return [("sell", tok, self)]
        return []

class MomentumTrader:
    def __init__(self, w: SimWallet): self.wallet = w; self.last_price = None
    def decide(self, price):
        if self.last_price is None: self.last_price = price; return []
        if price > self.last_price * 1.02 and self.wallet.sol > 0.01:
            amt = self.wallet.sol * 0.05; self.last_price = price
            return [("buy", amt, self)]
        elif price < self.last_price * 0.98 and self.wallet.tokens >= MIN_TRADE_TOKENS:
            amt = int(self.wallet.tokens * 0.1)
            if amt >= MIN_TRADE_TOKENS: self.last_price = price; return [("sell", amt, self)]
        self.last_price = price; return []

class Dev:
    def __init__(self, w: SimWallet): self.wallet = w
    def decide(self, phase, step):
        if phase == "BONDING" and step < 150 and self.wallet.sol > 0.01:
            amt = min(self.wallet.sol * 0.02, 0.3)
            return [("buy", amt, self)]
        return []

# ---------------------------------------------------------------------------
# 📊 BONDING CURVE
# ---------------------------------------------------------------------------
class BondingCurveSim:
    def __init__(self, virtual_sol=5.0, virtual_token=1e12,
                 real_sol=0.0, real_token=0.0):
        self.virtual_sol = virtual_sol
        self.virtual_token = virtual_token
        self.real_sol = real_sol
        self.real_token = real_token
        self.k = virtual_sol * virtual_token
    def buy(self, sol_in):
        if sol_in <= 0: return 0.0
        new_vsol = self.virtual_sol + sol_in
        new_vtok = self.k / new_vsol
        tok_out = self.virtual_token - new_vtok
        self.virtual_sol = new_vsol; self.virtual_token = new_vtok
        self.real_sol += sol_in; self.real_token += tok_out
        return tok_out
    def sell(self, token_in):
        if token_in <= 0: return 0.0
        token_in = min(token_in, self.real_token)
        new_vtok = self.virtual_token + token_in
        new_vsol = self.k / new_vtok
        sol_out = self.virtual_sol - new_vsol
        self.virtual_sol = new_vsol; self.virtual_token = new_vtok
        self.real_sol -= sol_out; self.real_token -= token_in
        return sol_out
    def price(self):
        if self.virtual_token == 0: return 0.0
        return self.virtual_sol / self.virtual_token * (10**TOKEN_DECIMALS)

# ---------------------------------------------------------------------------
# 🏊 AMM POOL – constant product, LP split across many devs
# ---------------------------------------------------------------------------
class AMMSim:
    def __init__(self, sol: float, token: float):
        self.sol = sol
        self.token = token
        self.k = sol * token
        self.lp_total = math.sqrt(sol * token)
        # LP split equally among all devs
        self.dev_lp = [self.lp_total / N_DEVS for _ in range(N_DEVS)]
    def price(self):
        if self.token == 0: return 0.0
        return self.sol / self.token * (10**TOKEN_DECIMALS)
    def remove_liquidity(self, dev_index, fraction_of_their_lp):
        dev_lp_available = self.dev_lp[dev_index]
        remove_lp = dev_lp_available * fraction_of_their_lp
        share = remove_lp / self.lp_total
        sol_out = self.sol * share
        token_out = self.token * share
        self.sol -= sol_out
        self.token -= token_out
        self.lp_total -= remove_lp
        self.dev_lp[dev_index] -= remove_lp
        self.k = self.sol * self.token
        return sol_out, token_out
    def sell_tokens(self, amount):
        """Dump tokens into the pool, receive SOL."""
        new_token = self.token + amount
        new_sol = self.k / new_token
        sol_out = self.sol - new_sol
        self.sol = new_sol
        self.token = new_token
        self.k = self.sol * self.token
        return sol_out

# ---------------------------------------------------------------------------
# 🎮 MAIN SIMULATION
# ---------------------------------------------------------------------------
curve = BondingCurveSim(virtual_sol=5.0, virtual_token=1e12)
sent = Sentiment()
phase = "BONDING"
migrated = False
amm = None

price_history = []
step_migrate = None
bleed_count = 0

# --- wallets scaled to ₦200k with variable sizes ---
dev_wallets = [SimWallet(1.68, 0)] + [SimWallet(random.uniform(0.3, 3.0), 0) for _ in range(N_DEVS-1)]
sniper_wallets = [SimWallet(random.uniform(0.5, 1.5), 0) for _ in range(N_SNIPERS)]
retail_wallets = [SimWallet(random.uniform(0.1, 0.5), 0) for _ in range(N_RETAIL)]
momentum_wallets = [SimWallet(0.2, 0) for _ in range(N_MOMENTUM)]

snipers = [Sniper(w) for w in sniper_wallets]
retails = [Retail(w) for w in retail_wallets]
momentums = [MomentumTrader(w) for w in momentum_wallets]
devs = [Dev(w) for w in dev_wallets]

plt.ion()
fig, ax = plt.subplots(figsize=(12,6))

print("🥷 Blood Jester ELITE – The Gangster Stealth Rug\n")

for step in range(STEPS):
    orders = []
    price = amm.price() if amm else curve.price()

    for s in snipers: orders.extend(s.decide(phase, step))
    for r in retails: orders.extend(r.decide(price, sent))
    for d in devs: orders.extend(d.decide(phase, step))
    for m in momentums: orders.extend(m.decide(price))

    buy_vol = sell_vol = 0.0

    for action, amount, agent in orders:
        if amount <= 0: continue
        if action == "buy":
            if agent.wallet.sol < amount: continue
            if not migrated:
                tok = curve.buy(amount)
                if tok <= 0: continue
                agent.wallet.sol -= amount
                agent.wallet.tokens += int(tok)
                buy_vol += amount
                if step % 200 == 0:
                    print(f"  🟢 {agent.__class__.__name__} bought {tok/10**TOKEN_DECIMALS:,.0f} tokens for {amount:.4f} SOL")
        else:
            if agent.wallet.tokens < amount: continue
            if not migrated:
                sol_out = curve.sell(amount)
                if sol_out <= 0: continue
                agent.wallet.tokens -= amount
                agent.wallet.sol += sol_out
                sell_vol += sol_out
                if step % 200 == 0:
                    print(f"  🔴 {agent.__class__.__name__} sold {amount/10**TOKEN_DECIMALS:,.0f} tokens for {sol_out:.4f} SOL")

    sent.update(price, sell_vol/(buy_vol+sell_vol+1e-9), 0.0, migrated)

    # ----- migration -----
    if not migrated and curve.real_sol >= MIGRATION_TARGET_SOL:
        migrated = True
        phase = "RAYDIUM"
        step_migrate = step
        amm = AMMSim(curve.real_sol, curve.real_token)
        print(f"\n🎯 TARGET REACHED at step {step}: {curve.real_sol:.2f} SOL raised!")
        print(f"   🌊 AMM pool created – {amm.sol:.2f} SOL, {amm.token/10**TOKEN_DECIMALS:,.0f} tokens")
        for i in range(N_DEVS):
            print(f"   💉 Dev {i+1} LP: {amm.dev_lp[i]:.2f} tokens ({amm.dev_lp[i]/amm.lp_total*100:.1f}%)")

    # ----- stealth bleed – randomised multi‑wallet, pre‑pumps, fake buys -----
    if migrated and step >= SLOW_BLEED_START:
        if random.randint(0, BLEED_INTERVAL_BASE*3) == 0:   # roughly every 6‑36 steps
            bleed_count += 1
            # pick a random dev with remaining LP
            active_devs = [i for i, lp in enumerate(amm.dev_lp) if lp > 0]
            if not active_devs:
                continue
            dev_idx = random.choice(active_devs)

            # Pre‑bleed pump candle (30% chance)
            if random.random() < PRE_BLEED_PUMP_PROB:
                pump_sol = random.uniform(PUMP_MIN, PUMP_MAX)
                new_sol = amm.sol + pump_sol
                new_token = amm.k / new_sol
                amm.sol = new_sol
                amm.token = new_token
                print(f"  📈 Pre‑bleed pump of {pump_sol:.4f} SOL (Dev {dev_idx+1})")

            # random LP removal fraction (2‑5%)
            fraction = random.uniform(0.02, 0.05)
            sol_out, tok_out = amm.remove_liquidity(dev_idx, fraction)
            dev_wallets[dev_idx].sol += sol_out
            dev_wallets[dev_idx].tokens += int(tok_out)

            # random dump %
            dump_frac = random.uniform(DUMP_FRACTION_MIN, DUMP_FRACTION_MAX)
            dump_amount = int(tok_out * dump_frac)
            if dump_amount > 0 and amm.token > 0:
                sol_from_dump = amm.sell_tokens(dump_amount)
                dev_wallets[dev_idx].sol += sol_from_dump
                dev_wallets[dev_idx].tokens -= dump_amount
                print(f"  🥷 Bleed #{bleed_count} (Dev {dev_idx+1}) – removed {sol_out:.4f} SOL, "
                      f"dumped {dump_amount/10**TOKEN_DECIMALS:,.0f} tokens for {sol_from_dump:.4f} SOL")
            else:
                print(f"  🥷 Bleed #{bleed_count} (Dev {dev_idx+1}) – removed {sol_out:.4f} SOL, no dump")

            # Fake buy after bleed (60% chance)
            if random.random() < FAKE_BUY_PROB:
                fake_sol = random.uniform(FAKE_BUY_MIN, FAKE_BUY_MAX)
                new_sol = amm.sol + fake_sol
                new_token = amm.k / new_sol
                amm.sol = new_sol
                amm.token = new_token
                print(f"  💨 Fake buy of {fake_sol:.4f} SOL placed (covers tracks)")

            sent.fear = min(1.0, sent.fear + 0.01)   # imperceptible rise

    price_history.append(amm.price() if amm else curve.price())

    if step % 200 == 0 or step == STEPS - 1:
        ax.clear()
        ax.plot(price_history, color="#10b981", lw=2, label="Blood Jester")
        if step_migrate is not None:
            ax.axvline(step_migrate, color="yellow", ls="--", label="Migration")
        if migrated:
            ax.axvspan(SLOW_BLEED_START, step, color="red", alpha=0.1, label="Stealth Bleed Zone")
        ax.set_title("🥷 Blood Jester ELITE – The Gangster Rug Pull")
        ax.set_xlabel("Step")
        ax.set_ylabel("Price (SOL per token)")
        ax.legend()
        ax.grid(alpha=0.2)
        plt.pause(0.01)

# ----- 💥 FINAL RUG : remove ALL remaining LP from all devs -----
if amm:
    for i in range(N_DEVS):
        if amm.dev_lp[i] > 0:
            sol_out, tok_out = amm.remove_liquidity(i, 1.0)
            dev_wallets[i].sol += sol_out
            dev_wallets[i].tokens += int(tok_out)
    print("\n💥 FINAL RUG – drained all remaining LP into devs' wallets")

print("\n" + "="*60)
print("✅ Blood Jester ELITE Stealth Rug complete!")
total_dev_sol = sum(d.sol for d in dev_wallets)
total_dev_tokens = sum(d.tokens for d in dev_wallets)
print(f"   🎒 Total dev SOL: {total_dev_sol:.2f} SOL")
print(f"   🪙 Total dev tokens: {total_dev_tokens/10**TOKEN_DECIMALS:,.0f} tokens")
print(f"   💰 Final price: {price_history[-1]:.10f} SOL per token")
print(f"   🩸 Total stealth bleeds: {bleed_count}")

sol_ngn_rate = 119107.19  # adjust to current rate
total_sol_value = total_dev_sol + total_dev_tokens * price_history[-1] / 10**TOKEN_DECIMALS
total_ngn = total_sol_value * sol_ngn_rate
print(f"   🏦 Total gangster haul: {total_sol_value:.2f} SOL ≈ ₦{total_ngn:,.2f}")
print("="*60)
plt.ioff()
plt.show()
