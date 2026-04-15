# Análisis adversarial — dependencia Kleros

> **Propósito**: identificar qué se rompe si adoptamos Curate + KlerosCore v2 como capa de submission/challenge/arbitration para ARGENTUM, bajo escenarios hostiles o de degradación del ecosistema Kleros.
>
> **Audiencia**: Seguridad (primero) → Auditoría (segundo) → Legales (tercero). Este doc alimenta la decisión OQ10 (migración parcial a Curate).
>
> **Estado**: análisis interno. No compartido.
> Última actualización: 2026-04-14.

---

## Alcance

Si seguimos el mapeo propuesto en `KLEROS_CURATE_MAPPING.md`:

- 5 Curate lists (2 Light + 3 Stake) desplegadas por nosotros, **apuntando a KlerosCore v2 Arbitrum One como arbitrador**
- ArgentumArbitrable.sol como hook IArbitrable consumiendo rulings
- ARGT como stake token en las 3 listas Stake Curate
- Meta-evidence en IPFS siguiendo ERC-1497

Las 3 piezas Kleros sobre las que nos apoyamos:

1. **KlerosCore v2 (contrato + jurados)** — fuente de rulings
2. **Light/Stake Curate (contratos)** — submission, challenge, bond lifecycle
3. **Subgraph Curate en The Graph** — indexación de items (Light Curate depende de esto para queries)

Extras que NO son Kleros pero entran por la puerta de atrás:
- **PNK** (token de governance de Kleros) — gobernanza de parámetros de court
- **IPFS** (via Kleros gateway + The Graph IPFS node) — persistencia de evidencia
- **Arbitrum One** — infraestructura L2 común, fuera de scope

---

## Escenarios adversariales

Cada escenario incluye: disparador, qué se rompe, probabilidad estimada, blast radius, mitigación.

### E1 — Kleros sube fees de arbitrage drasticamente

**Disparador**: gobernanza PNK vota aumento 5-10x en arbitration cost (por ejemplo para defender contra spam en un bull market).

**Qué se rompe**:
- Challenges de baja cuantía se vuelven economicamente irracionales
- El equilibrio "honest reporter bond returnable + reward" se rompe si el arbitration fee excede la reward
- Nuestras Light Curate lists (attestations, false actions, 3-5 ARGT de bond) quedan inutilizables

**Probabilidad**: MEDIA. Kleros ajusta periódicamente. Es decisión de governance, no unilateral.

**Blast radius**: alto. Sin challenges económicamente viables, Curate no filtra. Listas se envenenan con items spam.

**Mitigación**:
- Parametrizar bonds ARGENTUM como múltiplo variable del arbitration fee actual, no número fijo. Oracle-like read del fee on-chain antes de submit.
- Mantener **capa off-chain paralela** (argentum-core) como fallback: si Curate se degrada, seguimos operando karma economy sin interrupción.
- Monitoring: alert si arbitration fee cambia >20% vs baseline.

### E2 — Kleros cambia governance de forma adversa a agentes

**Disparador**: votación PNK que específicamente restringe el subcourt general para no aceptar disputas de "entidades no humanas" o similar.

**Qué se rompe**:
- Todos los rulings pendientes se paralizan
- Pérdida total de la capa de arbitrage

**Probabilidad**: BAJA. Kleros se posiciona explícitamente como neutral. Pero es un riesgo político real si hay backlash contra AI agents.

**Blast radius**: total para la dimensión arbitrage. Karma off-chain sigue operando.

**Mitigación**:
- ArgentumArbitrable ya es **IArbitrable-agnostic**: puede apuntar a cualquier Court compatible. Candidatos alternativos: Aragon Court (legacy pero funcional), Reality.eth + SafeSnap (oracle + multisig), UMA Optimistic Oracle.
- Documentar el switch path por escrito (migration runbook).
- Monitor Kleros governance forum por propuestas relevantes.

### E3 — KlerosCore v2 tiene un exploit / bug crítico

**Disparador**: vulnerabilidad que permite manipular rulings (por ejemplo, bribery detectable, error en appeal logic).

**Qué se rompe**:
- Rulings emitidos durante el período de exploit son no confiables
- Si confiamos el slashing a rulings manipulados, slasheamos agentes legítimos (irreversible en karma economy — aunque recomputable off-chain)

**Probabilidad**: BAJA-MEDIA. KlerosCore v2 tiene audits pero siempre hay riesgo residual.

**Blast radius**: alto en integridad reputacional; medio en ARGT (recuperable con fork del estado).

**Mitigación**:
- **No aplicar rulings automaticamente al karma off-chain**. Buffer de N horas (48h default) entre ruling Curate → slash efectivo. Si hay post-mortem Kleros en ese período, cancelamos el slash.
- Emergencia manual (via CEO + flujo Seg/Aud/Legales) para pausar procesamiento de rulings.
- Snapshot periódico del karma state on-chain para poder rollback.
- Monitor Kleros security disclosures + postmortems.

### E4 — Subgraph Curate deja de funcionar

**Disparador**: The Graph tiene outage o deprecia el subgraph de Light Curate.

**Qué se rompe**:
- Light Curate depende de subgraph para queries (no hay storage de campos on-chain)
- Submitters/challengers no pueden listar/buscar items
- Challenges coordinados se bloquean

**Probabilidad**: MEDIA. The Graph ha tenido outages puntuales; deprecation es política.

**Blast radius**: Light Curate queda casi inoperativo. Stake Curate sobrevive (almacena más on-chain).

**Mitigación**:
- Operar **nuestro propio subgraph indexer** (The Graph Hosted o node propio) sobre nuestros contratos Curate. Costo: infra ~50 USD/mes + mantenimiento.
- Usar **Stake Curate** preferentemente para datos críticos (ya era nuestra recomendación).
- IPFS primary storage redundante en nodo propio (no solo Kleros gateway).

### E5 — Kleros construye karma economy propia encima de Curate

**Disparador**: el equipo Kleros decide lanzar "KlerosReputation" como producto y compite directamente con ARGENTUM.

**Qué se rompe**:
- No rompe técnicamente nada — nuestros contratos siguen funcionando
- Rompe estratégicamente: nuestro diferencial se diluye, Kleros tiene brand+dist ventaja

**Probabilidad**: MEDIA. Fortunato mencionó "plans to use Curate for ERC-8004" sin partnership. Podrían ir solos.

**Blast radius**: estratégico, no operacional.

**Mitigación**:
- Nuestro diferencial REAL no es Curate — es:
  1. Off-chain karma economy rápida (micro-attestations sin bond)
  2. Integración MCP nativa (nuestros 5 servers en Anthropic Registry)
  3. Agent-first tooling (Ed25519 signing, Giskard stack completo)
  4. Community + creador context
- Curate es nuestra capa de disputes high-stake, no nuestra propuesta.
- Si Kleros compite, nos diferenciamos en profundidad de stack, no en ancho de oferta.

### E6 — ARGT pierde liquidez → Stake Curate se bloquea

**Disparador**: shock de mercado o migración masiva saca ARGT de circulación.

**Qué se rompe**:
- Agentes nuevos no pueden obtener ARGT para hacer stake
- Sybil/Identity/Attribution lists se congelan en onboarding
- Progressive protection amplifica el problema: items viejos tienen stakes crecientes, items nuevos no pueden empezar

**Probabilidad**: MEDIA (ARGT no tiene mercado robusto todavía).

**Blast radius**: alto para onboarding; medio para operaciones existentes.

**Mitigación** (ver también OQ15):
- Tesorería ARGT reserva para liquidity providing
- Faucet controlado para agentes nuevos con karma off-chain verificado (bridge karma→ARGT unidireccional mínimo)
- Revisar si vale permitir multi-token en Stake Curate (fallback a USDC)

### E7 — Progressive protection capturable

**Disparador**: atacante con capital inicia challenges baratos contra items legítimos de competidores para subir su stake y trabar liquidez.

**Qué se rompe**:
- Items legítimos quedan con stakes inflados que el submitter no pueden retirar
- Ataque económico indirecto sin violación de reglas

**Probabilidad**: MEDIA-ALTA. Es un ataque sutil, casi inevitable en cualquier Stake Curate maduro.

**Blast radius**: local por item. Si se coordina, puede ser sistémico.

**Mitigación**:
- Floor alto en challenge stake (30%+ del item stake) para hacer caro el ataque
- Ratio máximo item_stake / deposit_inicial (ej: cap en 10x) — más allá, submitter puede retirar automáticamente
- Monitor patterns: mismo challenger atacando múltiples items → alert

### E8 — Kleros decide deprecar Curate en favor de otra primitiva

**Disparador**: roadmap interno Kleros pivota (ya pasó con Curate Classic → Light).

**Qué se rompe**:
- Soporte (docs, frontend, subgraph) de la versión que usamos degrada
- Eventualmente deploys de parámetros nuevos dejan de funcionar

**Probabilidad**: BAJA-MEDIA en 1 año; ALTA en 3-5 años.

**Blast radius**: medio. Los contratos deployados siguen funcionando (Ethereum es inmutable), pero la UX se deteriora.

**Mitigación**:
- Mantener fork auto-hosteable de Curate dApp (es OSS).
- No depender de frontend Kleros para nuestro workflow primario — agentes interactúan via argentum-core, no via curate.kleros.io.

---

## Resumen de riesgos por impacto

| # | Escenario | Probabilidad | Blast radius | Prioridad mitigación |
|---|---|---|---|---|
| E1 | Fees suben drasticamente | Media | Alto | **ALTA** |
| E2 | Governance adversa a agentes | Baja | Total | **ALTA** |
| E3 | Exploit en KlerosCore | Baja-Media | Alto | **ALTA** |
| E4 | Subgraph falla | Media | Medio | Media |
| E5 | Kleros compite con nosotros | Media | Estratégico | Media |
| E6 | ARGT pierde liquidez | Media | Alto | **ALTA** |
| E7 | Progressive protection capturable | Media-Alta | Medio | Media |
| E8 | Curate deprecated | Baja (1yr) / Alta (5yr) | Medio | Baja (monitoreo) |

---

## Single points of failure identificados

1. **KlerosCore v2 contract**: única fuente de rulings autoritativos.
2. **Subgraph Curate en The Graph**: único índice queryable para Light Curate.
3. **ARGT liquidez**: único token de stake en listas Stake Curate (si elegimos A en mapping).
4. **Gobernanza PNK**: cambios de parámetros Court afectan nuestros costos.
5. **IPFS Kleros gateway**: si lo usamos como único pin, meta-evidencia se pierde si caen.

---

## Principios de diseño defensivo

Extraídos de los escenarios anteriores:

1. **Doble capa**: mantener **siempre** la capa off-chain (argentum-core karma economy) como primary fallback. Curate es mejora, no reemplazo.
2. **Agnostic por defecto**: ArgentumArbitrable apunta a una variable `arbitrator` — cualquier IArbitrable compatible sirve.
3. **Buffer antes del slash**: rulings Kleros no se aplican al karma state instantáneamente. 48h de ventana para post-mortem/emergencia.
4. **Subgraph propio**: deployar nuestro indexer sobre nuestros Curate lists, no depender del hosted de Kleros/Graph.
5. **IPFS multi-pin**: Kleros gateway + Pinata + nodo propio. Meta-evidencia nunca en un solo pin.
6. **Monitoring activo**: alerts sobre arbitration fee, governance forum Kleros, security disclosures, health del subgraph.
7. **Migration runbook por escrito**: pasos exactos para switchear a otro IArbitrable si se necesita (pre-escritos, no improvisados).
8. **Caps sobre progressive protection**: ratio máximo para evitar E7.

---

## Recomendación final

**La dependencia Kleros es aceptable SIEMPRE Y CUANDO** implementemos los 8 principios de diseño defensivo antes del switch a Curate en producción.

El argumento positivo: Curate nos ahorra 6+ meses de reinventar bond/challenge lifecycle, y los escenarios E3/E5 son aceptables porque el diferencial real de ARGENTUM no es Curate.

El argumento de rechazo: si no implementamos los 8 principios, un solo incidente E1/E3/E6 nos puede sacar del aire sin camino de recuperación. En ese caso mejor mantener la arquitectura actual off-chain + un IArbitrable minimal con appeals propios.

**Decisión pendiente por flujo Seg → Aud → Legales**: si avanzamos al switch, prerrequisitos son los 8 principios shippeados.

---

## Próximos pasos

1. **Seguridad (este doc)**: completar aprobación interna.
2. **Auditoría**: revisar mapping (KLEROS_CURATE_MAPPING.md) y este doc, confirmar consistencia.
3. **Legales**: especialmente relevante — ARGT como stake token introduce pregunta de security regulation (ver OQ abierto en dept_legales). Doc dedicado.
4. Cerrar OQ10 (migración parcial a Curate) con un GO/NO-GO formal solo después de los 3 anteriores.
