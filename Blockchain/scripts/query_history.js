const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  const provider = hre.ethers.provider;
  const infoPath = path.join(__dirname, "..", "deployment_info.json");
  const info = JSON.parse(fs.readFileSync(infoPath, "utf8"));
  const contract = await hre.ethers.getContractAt("ModelUpdateTracker", info.address);
  
  const currentRound = await contract.currentRound();
  console.log("Live On-Chain Current Round:", currentRound.toString());

  const filterLocal = contract.filters.LocalModelSubmitted();
  const filterGlobal = contract.filters.GlobalModelPublished();
  
  const locals = await contract.queryFilter(filterLocal, 0, "latest");
  const globals = await contract.queryFilter(filterGlobal, 0, "latest");

  const roundData = {};

  for (const l of locals) {
    const r = Number(l.args[0]);
    if (!roundData[r]) roundData[r] = { submissions: [], global: null };
    const receipt = await provider.getTransactionReceipt(l.transactionHash);
    roundData[r].submissions.push({
      hospital: roundData[r].submissions.length + 1,
      address: l.args[1],
      cid: l.args[2],
      txHash: l.transactionHash,
      blockNumber: l.blockNumber,
      gasUsed: receipt ? receipt.gasUsed.toString() : "0"
    });
  }

  for (const g of globals) {
    const r = Number(g.args[0]);
    if (!roundData[r]) roundData[r] = { submissions: [], global: null };
    const receipt = await provider.getTransactionReceipt(g.transactionHash);
    roundData[r].global = {
      cid: g.args[1],
      txHash: g.transactionHash,
      blockNumber: g.blockNumber,
      gasUsed: receipt ? receipt.gasUsed.toString() : "0"
    };
  }

  console.log("=== VERIFIED ROUND TRANSACTIONS FROM EVM ===");
  console.log(JSON.stringify(roundData, null, 2));
}

main().catch(console.error);
