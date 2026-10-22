/**
 * 🏥 Standalone Hospital Client Node Submission Script
 * Usage: node scripts/submit_hospital_model.js --hospital <1|2|3> --cid <CID> --hash <SHA256> [--private-key <HEX>]
 */
const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const args = process.argv.slice(2);
  let hospitalIndex = 0;
  let cid = "";
  let hash = "";
  let privateKey = null;

  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--hospital" && args[i + 1]) hospitalIndex = parseInt(args[++i], 10) - 1;
    else if (args[i] === "--cid" && args[i + 1]) cid = args[++i];
    else if (args[i] === "--hash" && args[i + 1]) hash = args[++i];
    else if (args[i] === "--private-key" && args[i + 1]) privateKey = args[++i];
  }

  if (!cid || !hash) {
    console.error("Usage: node scripts/submit_hospital_model.js --hospital <1|2|3> --cid <CID> --hash <SHA256>");
    process.exit(1);
  }

  const infoPath = path.join(__dirname, "..", "deployment_info.json");
  const info = JSON.parse(fs.readFileSync(infoPath, "utf8"));
  const contractAddress = info.address;

  let signer;
  if (privateKey) {
    signer = new hre.ethers.Wallet(privateKey, hre.ethers.provider);
  } else {
    const signers = await hre.ethers.getSigners();
    signer = signers[hospitalIndex + 1];
  }

  console.log(`🏥 Hospital Client Node: ${signer.address}`);
  const ModelUpdateTracker = await hre.ethers.getContractFactory("ModelUpdateTracker");
  const contract = ModelUpdateTracker.attach(contractAddress);

  const contrib = await contract.hospitalContributions(signer.address);
  if (!contrib.isRegistered) {
    throw new Error(`Node ${signer.address} is not registered or has been revoked on-chain.`);
  }

  const round = await contract.currentRound();
  const alreadySubmitted = await contract.hasSubmitted(round, signer.address);
  if (alreadySubmitted) {
    throw new Error(`Node ${signer.address} has already submitted for round ${round}.`);
  }

  console.log(`📤 Submitting local model for Round ${round}...`);
  console.log(`   CID: ${cid}`);
  console.log(`   SHA-256 Digest: ${hash}`);

  const tx = await contract.connect(signer).submitLocalModel(cid, hash);
  const receipt = await tx.wait();

  console.log(`✅ Submission successful!`);
  console.log(`   TxHash: ${receipt.hash}`);
  console.log(`   Block: #${receipt.blockNumber}`);
  console.log(`   Gas Used: ${receipt.gasUsed}`);
}

main().catch(err => {
  console.error("❌ Submission failed:", err.message || err);
  process.exit(1);
});
