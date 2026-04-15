# MOV-1 — Prototipo Kleros Curate v2 en arbitrumSepoliaDevnet

Fecha: 2026-04-15
Estado: PREP — listo para broadcast pendiente de go/no-go del creador.

## Objetivo

Ejecutar flujo end-to-end Curate v2 (Light Curate) en arbitrumSepoliaDevnet.
Output esperado para Fortunato: "ya probamos end-to-end, funciona asi" + tx hashes
+ link a la list en Curate app.

## Addresses — arbitrumSepoliaDevnet

### Kleros Core v2
```
KlerosCore                0x1Bd44c4a4511DbFa7DC1d5BC201635596E7200f9
DisputeResolver           0x71f8537e925C753Fe88DA7e69Ae423f9f3a9A292
DisputeTemplateRegistry   0xc852F94f90E3B06Da6eCfB61d76561ECfb94613f
EvidenceModule            0xA1F72e0445fc395A393247F5B8c958Ec9b7C0B49
DisputeKitClassic         0xeEEbbbff8f377dCFc7d4F7876C531db0d22720e1
```

### Curate v2
```
CurateFactory             0x24597B8918acA259337AdD2D2C2F07eafeaAf68e
CurateV2 (master impl)    0xD48fbC8B5149CBA5c7Ab6bfd37e7a04481475B59
CurateView                0xcB42d940a3c84e8d18dC45be8Fd93a1715bb0b81
```

### Wallet operativa
```
Deployer  0xDcc84E9798E8eB1b1b48A31B8f35e5AA7b83DBF4
Balance   0.369 ETH Sepolia (al 2026-04-15) — suficiente
```

## Factory.deploy signature

```solidity
function deploy(
    address _governor,                         // nuestra wallet deployer
    IArbitratorV2 _arbitrator,                 // KlerosCore Sepolia
    bytes _arbitratorExtraData,                // abi.encode(courtId, minJurors)
    address _connectedList,                    // address(0) — no connected list
    TemplateRegistryParams _templateRegistryParams,
    uint256[4] _baseDeposits,                  // ver abajo
    uint256 _challengePeriodDuration,          // segundos
    address _relayerContract,                  // address(0) — sin relayer
    string _listMetadata                       // IPFS URI o JSON inline corto
)

struct TemplateRegistryParams {
    address templateRegistry;                  // DisputeTemplateRegistry Sepolia
    string[2] registrationTemplateParameters;  // [templateData, dataMappings]
    string[2] removalTemplateParameters;       // [templateData, dataMappings]
}
```

## Parametros propuestos (requieren OK creador)

### _arbitratorExtraData
`abi.encode(uint96(1), uint96(3))`
- courtId = 1 (general court, default)
- minJurors = 3 (minimo para testnet; en mainnet subiriamos)

### _baseDeposits uint256[4]
Orden esperado segun spec Curate v2:
```
[0] submissionBaseDeposit           0.001 ETH
[1] removalBaseDeposit              0.001 ETH
[2] submissionChallengeBaseDeposit  0.001 ETH
[3] removalChallengeBaseDeposit     0.001 ETH
```
Racional: en testnet no necesitamos bonds reales. 0.001 ETH permite
ejecutar varios submits+challenges con el saldo actual (369 / 0.001 = 369
operaciones teoricas antes de quedarnos sin).

### _challengePeriodDuration
`3600` segundos (1 hora). Para testnet. En mainnet subiriamos a 3-7 dias.

### _listMetadata
```json
{
  "tcrTitle": "ARGENTUM Attestations (testnet prototype)",
  "tcrDescription": "Prototype list for ERC-8004 agent attestations. Testnet only.",
  "columns": [
    {"label": "agentId", "type": "number", "isIdentifier": true},
    {"label": "actionHash", "type": "text"},
    {"label": "evidenceURI", "type": "link"}
  ],
  "itemName": "attestation",
  "itemNamePlural": "attestations",
  "logoURI": "",
  "requireRemovalEvidence": true
}
```
Se sube a IPFS y se pasa el URI como `_listMetadata`.

### Templates (metaEvidence ERC-1497 v2)
Registration + removal templates basados en `argentum-core/metaEvidence.template.json`
pero simplificados para el prototype (solo attestation type).

## Plan de ejecucion por tx

### Fase 1 — Preparacion (off-chain, gratis)
- [ ] Generar listMetadata JSON final
- [ ] Generar registrationTemplate + removalTemplate (metaEvidence simplificado)
- [ ] Upload metaEvidence a IPFS (pinata + kleros gateway)
- [ ] Verificar URIs accesibles

### Fase 2 — Deploy instance (1 tx)
- [ ] Llamar `CurateFactory.deploy(...)` con params arriba
- [ ] Capturar address del Curate instance creado
- [ ] Verificar en arbiscan sepolia

### Fase 3 — Submit test item (1 tx)
- [ ] Construir item data (agentId=1 del GiskardIdentityRegistry, actionHash mock, evidenceURI)
- [ ] Llamar `curateInstance.addItem(itemData)` + value = submissionBaseDeposit + arbitrationCost
- [ ] Capturar itemID

### Fase 4 — Challenge (1 tx)
- [ ] Desde la misma wallet (testnet, simulamos adversario), llamar `challengeRequest(itemID, evidence)` + value
- [ ] Capturar disputeID

### Fase 5 — Ruling (vote simulation)
- [ ] En testnet Kleros los jurados son automaticos o manuales via UI
- [ ] Esperar challenge period + commit+reveal period
- [ ] Verificar ruling emitido
- [ ] Verificar item status final

### Fase 6 — Documentar
- [ ] Grabar gif / screen recording del item en curate.kleros.io (UI testnet)
- [ ] README con tx hashes + links
- [ ] Draft mensaje a Fortunato (no enviar — queda en hold hasta que conteste REV5)

## Riesgos

1. **Bonds insuficientes** — si el Curate exige bonds minimos on-chain
   para cubrir arbitrationCost, 0.001 ETH puede fallar. Mitigacion:
   consultar `KlerosCore.arbitrationCost(extraData)` antes de deployar
   y setear baseDeposit >= arbitrationCost.

2. **Template format incorrecto** — templates ERC-1497 tienen schema
   estricto. Mitigacion: copiar template publico de otra list Sepolia
   que funcione y adaptar.

3. **CourtId 1 no existe o no acepta disputes** — testnet devnet puede
   tener configs distintas. Mitigacion: leer `KlerosCore.getCourt(1)`
   antes.

4. **Broadcast con params mal** — irreversible en el sentido de que
   queda una list mal configurada. Mitigacion: podemos simplemente
   desplegar otra. Costo: ~0.002 ETH testnet por deploy. Aceptable.

## Decisiones pendientes creador

- [ ] OK con parametros propuestos (bonds, challenge period, courtId, minJurors)
- [ ] ¿Hacemos upload a IPFS con cuenta Pinata existente o montamos nodo propio
      para esto?
- [ ] ¿Ejecutamos hoy o partimos en 2 sesiones (prep + broadcast)?

## Proximos archivos a escribir

- `giskard-payments/script/DeployCurateSepoliaPrototype.s.sol` — Foundry script
- `argentum-core/docs/curate-sepolia/listMetadata.json`
- `argentum-core/docs/curate-sepolia/registrationTemplate.json`
- `argentum-core/docs/curate-sepolia/removalTemplate.json`
