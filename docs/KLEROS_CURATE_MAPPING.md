# Kleros Curate — Mapeo a ARGENTUM

> **Estado**: documento interno de análisis. NO compartido con Kleros todavía.
> Se usa para informar las próximas respuestas a Fortunato y la eventual decisión arquitectónica OQ10.
> Última actualización: 2026-04-14.

---

## Las tres variantes de Curate

Kleros tiene tres versiones de Curate. Elegir cuál usar no es trivial — cambia costos, incentivos y modelo de verificación.

### Classic Curate

Versión original. **Almacena el item completo en storage del contrato** (O(n) en espacio). Permite queries on-chain contract-to-contract sobre los campos del item.

- Costo deploy: ~7M gas
- Ventaja: composable on-chain (otros contratos pueden leer campos)
- Desventaja: caro en cualquier L2 y prohibitivo en mainnet
- Obsoleto para casi todo use case moderno

### Light Curate

Optimización. **Solo almacena el IPFS multihash del item**; los datos viven en IPFS + The Graph subgraph.

- Costo deploy: ~700k gas (10x más barato, EIP-1167 minimal proxy)
- Query: via subgraph (off-chain pero indexado)
- Desventaja: no hay composability on-chain de campos — otro contrato no puede leer "dame todos los items con tag X"
- Bounds: bond clásico de Curate (se paga al submit; se devuelve si nadie challenge ni gana challenge)
- Challenge: período fijo; si nadie challenge, item queda accepted

### Stake Curate

**Novedad 2025** (deployado en Gnosis agosto 2025, primera implementación DAMM Capital septiembre 2025).

Cambio conceptual clave: **el deposit es permanente**, no expira después del challenge period.

- Submit: submitter loca ERC-20 (cualquiera, configurable) en el contrato — indefinidamente
- El item queda "verified" después del período de aceptación
- **Cualquiera puede challenge en cualquier momento, para siempre**
- Challenger stakea un % del item stake + arbitration fee
- Si challenger gana: se lleva el item stake completo como bounty; item se borra
- Si submitter gana: challenger stake se SUMA al item stake (**progressive protection**: cada ataque fallido encarece el próximo)
- Withdrawal: submitter puede retirar, pero pasa por waiting period donde cualquiera puede challenge

Trade-offs:
- **Ventaja**: incentivo continuo de accuracy + bounty hunter natural que limpia bad items + capital cada vez más pesado defiende items legítimos
- **Desventaja**: capital permanente bloqueado (puede ser oneroso para items de bajo valor) + la liquidez se atomiza en miles de items
- **Ideal para**: reputación, identidad, compliance, cualquier claim que deba mantenerse true en el tiempo

---

## Postura ARGENTUM: qué variante para qué

| Dispute type | Variante recomendada | Razón |
|---|---|---|
| **Attestation** (basic action claim, high-volume) | **Light Curate** | Bajo valor por item, alto volumen, período corto de relevancia. Caro bloquear capital permanente en millones de attestations |
| **False Action** (claim exagerado/fabricado) | **Light Curate** | Misma lógica — action es evento puntual, no claim continuo |
| **Attribution** (authorship) | **Stake Curate** | Claim es permanente ("yo escribí X"); tiene sentido que el deposit también lo sea. Attacker que quiera cambiar attribution paga más cada vez |
| **Sybil / Single Entity Proof** | **Stake Curate** | Identidad única es claim que debe mantenerse verificable indefinidamente. Progressive protection aquí es oro: cada sybil-attack fallido encarece el siguiente |
| **Identity binding** (agent pubkey ↔ entity) | **Stake Curate** | Idem — binding persistente, claim atemporal |

Resultado: **arquitectura híbrida de 2 Light Curate + 3 Stake Curate lists.**

### Requirements anidados

Fortunato señaló que Curate permite composición. Nuestro gating propuesto:

- Submit a **Attestation list** requiere: holder de **Single Entity Proof**
- Submit a **Attribution list** requiere: holder de **Identity Binding** + karma ≥ umbral
- Submit a **Identity Binding** requiere: solo bond ARGT mínimo (entrada baja, pero progressive stake sube si hay challenges)

Esto convierte la sybil resistance en gate de facto: no podés inflar karma sin primero probar que sos entidad única.

---

## Pregunta 2 (de REV3) — karma como non-token stake

**Pregunta que le dejamos a Fortunato**: "¿hay pattern en Curate para usar non-token stake (e.g. karma del agente bloqueado) en vez de un token que represente el karma?"

**Autoanalísis**:

Mirando Stake Curate, el deposit **debe** ser ERC-20. No hay pattern de "non-token stake" puro. Pero hay dos caminos:

### Camino A: ARGT como stake token (recomendado)

ARGT ya existe como ERC-20 en Arbitrum One (contrato 0xD467...). Si configuramos Stake Curate con ARGT como deposit token, entonces:

- "Bloquear karma" = bloquear ARGT
- Slashing = transfer de ARGT del submitter al challenger
- Progressive protection = cada challenge fallido suma ARGT al item stake

Esto es **operacionalmente equivalente** a "karma como stake", con la ventaja de ser nativo a Curate sin modificar nada.

Pregunta de diseño: hoy karma se registra off-chain en argentum-core, y ARGT es un token separado. ¿Un agente con karma = 1000 recibe automáticamente 1000 ARGT? Si sí (bridging karma → ARGT), el loop cierra. Si no, Stake Curate requiere que el agente ya tenga ARGT separado, desacoplando karma de stake.

Decisión pendiente: **diseñar el bridge karma ↔ ARGT formalmente**. Esto es un OQ que emerge.

### Camino B: wrapper contract que re-encapsula karma

Podríamos escribir un KarmaStakeWrapper que:
- Acepta el karma off-chain del agente (vía signed message con Ed25519)
- Emite un NFT "karma lock" que representa el karma locked
- Ese NFT se usa como el "stake" en una versión modificada de Curate

**Problema**: esto NO es Stake Curate oficial. Sería fork. Perdemos el stack mantenido por Kleros.

**Veredicto**: A es el camino realista. B es un ejercicio teórico.

### Respuesta tentativa a Fortunato (cuando venga el turno)

> "Thinking about your question on non-token stake: we don't see a clean way to do it without forking Curate. What we're converging on is using ARGT (our existing ERC-20) as the stake token in Stake Curate, and building the bridge from off-chain karma → on-chain ARGT for agents that need to participate in high-stake lists. That keeps us on the supported Curate path. Does that match what you'd recommend, or are we missing a pattern?"

---

## Mapeo concreto — parámetros por lista (draft)

Estos son tentativos y se ajustan después del feedback de Fortunato.

### Lista 1 — Attestation (Light Curate)

- Deposit: 5 ARGT por submission
- Challenge period: 48 horas
- Challenger bond: 5 ARGT
- Arbitration: KlerosCore v2 Arbitrum One (dirección pendiente)
- Meta-evidence: metaEvidence.template.json (dispute_type = false_attestation)
- Requirements: holder de Single Entity Proof (Lista 3)

### Lista 2 — Attribution (Stake Curate)

- Deposit mínimo: 100 ARGT (permanente)
- Challenger stake: 25% del item stake
- Arbitration fee: ~0.002 ETH
- Withdrawal period: 7 días
- Requirements: Identity Binding (Lista 5)

### Lista 3 — Single Entity Proof (Stake Curate)

- Deposit mínimo: 40 ARGT (permanente) — alineado con ejemplo que dio Fortunato ("Single Entity Proof = 40 USD")
- Challenger stake: 30%
- Withdrawal period: 14 días
- Requirements: bond ARGT base + evidencia off-chain (KYC opcional, prueba biométrica, etc.)

### Lista 4 — False Action (Light Curate)

- Similar a Lista 1 pero con evidence_expected distinto
- Deposit: 3 ARGT
- Challenge period: 72 horas

### Lista 5 — Identity Binding (Stake Curate)

- Deposit mínimo: 20 ARGT
- Challenger stake: 30%
- Withdrawal period: 14 días

---

## Impacto sobre ArgentumArbitrable

Con Curate absorbiendo submission + challenge + bond handling:

- ArgentumArbitrable.sol **se simplifica**: solo necesita el hook IArbitrable (recibir ruling de la corte). No necesita reward split, no necesita bond lifecycle. 50 líneas menos.
- El flujo karma slashing sigue siendo nuestro: cuando Curate ejecuta ruling → emitimos evento `KarmaSlashed(agent, amount)` → argentum-core lo consume y actualiza el karma off-chain.
- On-chain karma (ARGT) se slashea automáticamente vía el stake lifecycle de Curate.

---

## Riesgos adversariales de este diseño

1. **ARGT liquidez**: si 3 listas son Stake Curate con deposits permanentes, mucho ARGT queda locked. ¿Hay suficiente circulante?
2. **Progressive protection capturable**: un atacante puede intencionalmente perder un challenge barato para subir el item stake de un item legítimo rival y trabar su liquidez. Mitigación: tamaño mínimo de challenge stake alto.
3. **Bridge karma → ARGT**: si no lo implementamos bien, un agente con karma alto off-chain pero pocos ARGT no puede defenderse de challenges. Mitigación: el bridge debe ser 1:1 y automático sobre acciones verificadas.
4. **Dependencia Kleros**: ya listado en BITACORA Kleros integracion.

---

## Próximos pasos

1. Leer los contratos Stake Curate directamente (github.com/kleros/stake-curate) para verificar que los parámetros que asumimos existen.
2. Localizar KlerosCore v2 Arbitrum One address (OQ del movimiento 4).
3. Cuando Fortunato responda pregunta 1 (Light vs Stake), contrastar con esta postura. Si coincide, tenemos mapeo. Si difiere, ajustar.
4. Cuando Fortunato responda pregunta 2, contrastar con el Camino A/B. Si confirma A, empezar diseño del bridge karma ↔ ARGT.
5. Eventualmente: deployar las 5 listas en testnet (Sepolia Arbitrum) antes de commit a mainnet.
