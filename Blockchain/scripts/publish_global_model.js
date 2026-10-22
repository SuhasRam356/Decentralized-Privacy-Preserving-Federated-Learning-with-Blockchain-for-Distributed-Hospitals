/**
 * 🌍 Standalone Central Aggregator Publishing Script
 * Usage: node scripts/publish_global_model.js --cid <CID> --hash <SHA256> [--private-key <HEX>]
 */
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const args = process.argv.slice(2);
  let cid = "";
  let hash = "";
  let privateKey = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--cid" && args[i + 1]) cid = args[++i];
    else if (args[i] === "--hash" && args[i + 1]) hash = args[++i];
    else if (args[i] === "--private-key" && args[i + 1]) privateKey = args[++i];
  }

  if (!cid || !hash) {
    console.error("Usage: node scripts/publish_global_model.js --cid <CID> --hash <SHA256>");
    process.exit(1);
  }

  const infoPath = path.join(__dirname, "..", "deployment_info.json");
  const info = JSON.parse(fs.readFileSync(infoPath, "utf8"));
  const contractAddress = info.address;

  let aggregator;
  if (privateKey) {
    aggregator = new hre.ethers.Wallet(privateKey, hre.ethers.provider);
  } else {
    const signers = await hre.ethers.getSigners();
    aggregator = signers[0];
  }

  console.log(`🌍 Central Aggregator: ${aggregator.address}`);
  const ModelUpdateTracker = await hre.ethers.getContractFactory("ModelUpdateTracker");
  const contract = ModelUpdateTracker.attach(contractAddress);

  const round = await contract.currentRound();
  const req = await contract.requiredSubmissions();
  const roundHospitals = await contract.getRoundHospitals(round);

  console.log(`⛓️  Round ${round}: Received ${roundHospitals.length}/${req} required submissions.`);
  if (roundHospitals.length < req) {
    throw new Error(`Quorum not reached: ${roundHospitals.length} < ${req}. Cannot publish global model.`);
  }

  console.log(`🌍 Publishing global model checkpoint...`);
  console.log(`   CID: ${cid}`);
  console.log(`   SHA-256: ${hash}`);

  const tx = await contract.connect(aggregator).publishGlobalModel(cid, hash);
  const receipt = await tx.wait();

  const newRound = await contract.currentRound();
  console.log(`✅ Global model published successfully!`);
  console.log(`   TxHash: ${receipt.hash}`);
  console.log(`   Block: #${receipt.blockNumber}`);
  console.log(`   Gas Used: ${receipt.gasUsed}`);
  console.log(`🎉 Protocol advanced to Round ${newRound}`);
}

main().catch(err => {
  console.error("❌ Aggregator publication failed:", err.message || err);
  process.exit(1);
});
