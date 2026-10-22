const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const inputArg = process.env.ROUND_DATA || process.argv[2];
  if (!inputArg) {
    throw new Error("No round data provided.");
  }

  const roundData = JSON.parse(inputArg);
  const infoPath = path.join(__dirname, "..", "deployment_info.json");
  const info = JSON.parse(fs.readFileSync(infoPath, "utf8"));
  const contractAddress = info.address;

  const ModelUpdateTracker = await hre.ethers.getContractFactory("ModelUpdateTracker");
  const contract = ModelUpdateTracker.attach(contractAddress);

  const signers = await hre.ethers.getSigners();
  const owner = signers[0];
  const hospitalSigners = [signers[1], signers[2], signers[3]];

  const round = await contract.currentRound();
  const requiredSubmissions = await contract.requiredSubmissions();
  const activeCount = await contract.activeHospitalCount();

  console.log(`⛓️  Connected to ModelUpdateTracker: ${contractAddress}`);
  console.log(`🔢 Current on-chain round: ${round}`);
  console.log(`👥 Active registered hospitals: ${activeCount} (Quorum required: ${requiredSubmissions})`);

  const results = [];
  for (const sub of roundData.submissions) {
    const signer = hospitalSigners[sub.hospitalIndex];
    if (!signer) {
      console.warn(`⚠️ No signer configured for hospital index ${sub.hospitalIndex}`);
      continue;
    }

    // Check registration status on-chain — RESPECT REVOCATION
    const contrib = await contract.hospitalContributions(signer.address);
    if (!contrib.isRegistered) {
      console.log(`🚫 Hospital Node ${sub.hospitalIndex + 1} (${signer.address}) is REVOKED/UNREGISTERED on-chain. Skipping.`);
      continue;
    }

    const alreadySubmitted = await contract.hasSubmitted(round, signer.address);
    if (alreadySubmitted) {
      console.log(`ℹ️ Hospital Node ${sub.hospitalIndex + 1} (${signer.address}) already submitted for Round ${round}. Skipping.`);
      continue;
    }

    console.log(`📤 Node ${sub.hospitalIndex + 1} signing submitLocalModel(${sub.cid.slice(0, 10)}...)...`);
    const tx = await contract.connect(signer).submitLocalModel(sub.cid, sub.hash);
    const receipt = await tx.wait();
    console.log(`   ✓ Tx Confirmed: ${receipt.hash} (Block #${receipt.blockNumber}, Gas: ${receipt.gasUsed})`);

    results.push({
      hospital: sub.hospitalIndex + 1,
      address: signer.address,
      txHash: receipt.hash,
      blockNumber: receipt.blockNumber,
      gasUsed: receipt.gasUsed ? receipt.gasUsed.toString() : "0",
      cid: sub.cid,
      hash: sub.hash
    });
  }

  // Verify that quorum is met before calling publishGlobalModel
  const roundHospitals = await contract.getRoundHospitals(round);
  if (roundHospitals.length < requiredSubmissions) {
    throw new Error(
      `Quorum not met for Round ${round}: received ${roundHospitals.length} submissions, requires ${requiredSubmissions}.`
    );
  }

  // Publish global model as aggregator
  console.log(`🌍 Central Aggregator (${owner.address}) signing publishGlobalModel...`);
  const globalTx = await contract.connect(owner).publishGlobalModel(roundData.global.cid, roundData.global.hash);
  const globalReceipt = await globalTx.wait();
  console.log(`   ✓ Global Model Tx: ${globalReceipt.hash} (Block #${globalReceipt.blockNumber}, Gas: ${globalReceipt.gasUsed})`);

  const newRound = await contract.currentRound();
  console.log(`🎉 Round advanced on-chain to: ${newRound}`);

  // Write immutable round receipt manifest
  const manifestPath = path.join(__dirname, "..", "round_receipt.json");
  fs.writeFileSync(manifestPath, JSON.stringify({
    round: Number(round),
    newRound: Number(newRound),
    contractAddress,
    submissions: results,
    globalModel: {
      cid: roundData.global.cid,
      hash: roundData.global.hash,
      txHash: globalReceipt.hash,
      blockNumber: globalReceipt.blockNumber,
      gasUsed: globalReceipt.gasUsed ? globalReceipt.gasUsed.toString() : "0"
    },
    timestamp: new Date().toISOString()
  }, null, 2));

  console.log(`💾 Round manifest written to round_receipt.json`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ On-chain round orchestration failed:", err);
    process.exit(1);
  });
