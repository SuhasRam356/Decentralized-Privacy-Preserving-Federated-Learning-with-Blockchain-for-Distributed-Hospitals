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
  console.log(`⛓️  Current on-chain round: ${round}`);

  const results = [];
  for (const sub of roundData.submissions) {
    const signer = hospitalSigners[sub.hospitalIndex];
    console.log(`📤 Submitting local model for Hospital ${sub.hospitalIndex + 1} (${signer.address})...`);
    const tx = await contract.connect(signer).submitLocalModel(sub.cid, sub.hash);
    const receipt = await tx.wait();
    console.log(`   ✓ Tx Hash: ${receipt.hash} (Gas used: ${receipt.gasUsed})`);
    results.push({
      hospital: sub.hospitalIndex + 1,
      address: signer.address,
      txHash: receipt.hash,
      cid: sub.cid,
      hash: sub.hash
    });
  }

  // Publish global model
  console.log(`🌍 Aggregator (${owner.address}) publishing global model...`);
  const globalTx = await contract.connect(owner).publishGlobalModel(roundData.global.cid, roundData.global.hash);
  const globalReceipt = await globalTx.wait();
  console.log(`   ✓ Global Model Tx: ${globalReceipt.hash}`);

  const newRound = await contract.currentRound();
  console.log(`🎉 Round advanced to: ${newRound}`);

  // Write round receipt manifest
  const manifestPath = path.join(__dirname, "..", "round_receipt.json");
  fs.writeFileSync(manifestPath, JSON.stringify({
    round: Number(round),
    newRound: Number(newRound),
    contractAddress,
    submissions: results,
    globalModel: {
      cid: roundData.global.cid,
      hash: roundData.global.hash,
      txHash: globalReceipt.hash
    },
    timestamp: new Date().toISOString()
  }, null, 2));

  console.log(`💾 Round manifest written to round_receipt.json`);
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ On-chain round submission failed:", err);
    process.exit(1);
  });
