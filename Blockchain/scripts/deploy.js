const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const REQUIRED_SUBMISSIONS = 3;

  console.log("🚀 Deploying ModelUpdateTracker...");

  const ModelUpdateTracker =
    await hre.ethers.getContractFactory("ModelUpdateTracker");

  const contract =
    await ModelUpdateTracker.deploy(REQUIRED_SUBMISSIONS);

  await contract.waitForDeployment();

  const address = await contract.getAddress();
  const owner = await contract.owner();
  const round = await contract.currentRound();

  console.log("✅ Contract deployed");
  console.log("📍 Address:", address);
  console.log("🔢 Current round:", round.toString());

  const signers = await hre.ethers.getSigners();
  const hospitalAddresses = [
    signers[1].address,
    signers[2].address,
    signers[3].address
  ];

  console.log("🏥 Registering default test hospital nodes...");
  for (let i = 0; i < hospitalAddresses.length; i++) {
    const tx = await contract.registerHospital(hospitalAddresses[i]);
    await tx.wait();
    console.log(`   ✓ Hospital ${i + 1} registered: ${hospitalAddresses[i]}`);
  }

  const info = {
    address,
    owner,
    requiredSubmissions: REQUIRED_SUBMISSIONS,
    hospitals: hospitalAddresses,
    network: hre.network.name,
    deployedAt: new Date().toISOString()
  };

  const outPath = path.join(__dirname, "..", "deployment_info.json");
  fs.writeFileSync(outPath, JSON.stringify(info, null, 2));

  console.log("💾 deployment_info.json written");
}

main()
  .then(() => process.exit(0))
  .catch((err) => {
    console.error("❌ Deploy failed:", err);
    process.exit(1);
  });
