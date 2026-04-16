# KARMA ↔ ARGT Bridge — Design Doc v0

**Autor:** Giskard (CEO Rama)
**Fecha:** 2026-04-15
**Estado:** Draft — interno, no compartir
**Bloqueante de:** Stake Curate Arbitrum One deploy (requiere ARGT como ERC20 collateral)

## Contexto

- `karma` vive off-chain en `argentum-core` (SQLite, tabla `entities`). Se gana por acciones verificadas por attestors (peso karma-weighted, threshold 2.0). Genesis attestors: lightning, giskard-self.
- `ARGT` vive on-chain en Arbitrum One (`0x42385c1038f3fec0ecCFBD4E794dE69935e89784`). ERC20 estándar. **totalSupply = 0**. Owner = deployer (`0xDcc84...`).
- Kleros Stake Curate soporta ERC20 collateral → ARGT es viable **si tiene liquidez y significado económico real**.

El bridge define cómo — y si — karma off-chain se convierte en ARGT on-chain.

## Opciones

### A — Peg 1:1 (mint on verify, burn on slash)

Cada acción verificada mintea ARGT al poster; cada slash quema ARGT.

- **Pro:** simple, karma = ARGT, una sola métrica.
- **Contra:** ARGT se vuelve **security** casi garantizado (Howey: expectativa de ganancia por esfuerzo ajeno — verificadores). MiCA lo clasifica como asset-referenced o utility ambiguo. **Riesgo regulatorio terminal.**
- **Adversarial:** sybil farming de karma = mint infinito. Slashing no alcanza si el atacante ya retiró ARGT al mercado.

### B — ARGT separado, redención por claim

karma acumula off-chain; usuario puede "canjear" N karma → M ARGT vía claim firmado por oracle (giskard-self).

- **Pro:** desacopla emisión de acción individual; permite ratios dinámicos.
- **Contra:** oracle centralizado (giskard-self firma) = single point of trust. Sigue siendo security-shaped.
- **Adversarial:** si el oracle cae o es comprometido, mint ilimitado.

### C — ARGT = stake token, karma = reputation (sin conversión)

ARGT solo se compra/gana por bounties, **nunca por karma directo**. karma queda como reputación pura off-chain. ARGT funciona como collateral en Stake Curate y pago de servicios.

- **Pro:** karma no es tokenizable → **no security**. ARGT es utility puro (collateral + medio de pago). Separa reputación de capital.
- **Contra:** necesitamos otro mecanismo para dar ARGT inicial (bounties, liquidity mining, venta). Más trabajo.
- **Adversarial:** más robusto — atacar karma no da ARGT, atacar ARGT no da reputación.

### D — One-way karma→ARGT, sin redeem

Mint karma→ARGT con cap mensual y rate limit. ARGT no reconvierte a karma.

- **Pro:** recompensa contributors sin ciclo reflexivo.
- **Contra:** sigue siendo security por construcción. Cap mitiga pero no elimina.

## Criterio de los cuatro

| | A (peg) | B (claim) | **C (separados)** | D (one-way cap) |
|---|---|---|---|---|
| **Elon (ejecutable)** | Fácil código, difícil legal | Medio | Medio — requiere bounty program | Fácil |
| **Vitalik (incentivos)** | Rompe — farmear karma es rentable | Frágil por oracle | **Sano — karma es señal, ARGT es capital** | Aceptable con cap |
| **Peter (escala)** | Explota o muere regulado | Escala con oracle fragil | **Escala — dos activos, dos usos** | Escala limitado por cap |
| **Dario (seguro)** | Inseguro — sybil + regulatorio | Inseguro — oracle | **Seguro — superficies separadas** | Medio |

## Recomendación

**Opción C** — karma y ARGT separados, **sin bridge directo**.

- karma = reputación pura, off-chain, no transferible, no monetizable por diseño.
- ARGT = utility token on-chain para: collateral Stake Curate, pago de servicios Mycelium (memory, search, oasis), bounties por contribuciones auditadas.
- Distribución inicial ARGT: bounty program (contribuidores reciben ARGT por PRs mergeados + audits verificados, con flow Seg→Aud→Legales), no mint automático.
- karma alto = **prioridad** para recibir bounties ARGT, no conversión directa.

Esto mantiene ARGT defendible como utility y karma libre de framing financiero.

## Open questions para Legales

- ¿Bounty program con ARGT califica como compensación laboral / security en AR/US/EU?
- ¿"Priority by karma" para bounties crea expectativa suficiente para Howey?
- ¿Necesitamos whitepaper ARGT defensivo antes de cualquier transferencia a terceros?

## Flujo Seg → Aud → Legales

- **Seg:** revisar vectores sybil sobre karma (ya parcialmente cubierto: rate limit + slashing). Añadir: monitoreo de patrones de attestation cross-entity.
- **Aud:** verificar que ningún código on-chain actual tiene path `karma → ARGT mint`. Confirmado: `giskard-payments/src` no tiene mint/burn ARGT hoy.
- **Legales:** abrir dictamen sobre Opción C + bounty program antes de primer transfer.

## Bloqueos a desbloquear

- **OQ15 (liquidez ARGT Stake Curate):** aliviado — Light Curate usa ETH; Stake solo presiona si decidimos deployar lista propia. Con Opción C, ARGT se distribuye vía bounties ≠ liquidez de mercado. Requiere decisión separada: ¿listamos ARGT en DEX Arbitrum o mantenemos circuito cerrado?
- **OQ16 (quién deploya Stake Curate):** postergable hasta tener ARGT con liquidez mínima.

## Próximo paso

Consultar al creador. No ejecutar nada hasta visto bueno + flow Seg→Aud→Legales cerrado.
