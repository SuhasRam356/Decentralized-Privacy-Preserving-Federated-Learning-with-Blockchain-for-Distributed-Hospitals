const fs = require("fs");

/**
 * Test IPFS connections for all hospital nodes
 */
async function testIPFSConnection(apiUrl, nodeName) {
  try {
    console.log(`\n🔍 Testing ${nodeName} (${apiUrl})...`);
    
    // Dynamic import for ESM ipfs-http-client
    let create;
    try {
      const ipfsModule = await import("ipfs-http-client");
      create = ipfsModule.create;
    } catch {
      // Fallback
    }

    if (create) {
      const ipfs = create({ url: apiUrl });
      const version = await ipfs.version();
      console.log(`   ✅ Connected! IPFS version: ${version.version}`);
      const id = await ipfs.id();
      const idStr = id.id.toString();
      console.log(`   ✅ Node ID: ${idStr.substring(0, 20)}...`);
      const testContent = Buffer.from(`Test file for ${nodeName} - ${new Date().toISOString()}`);
      const result = await ipfs.add(testContent, { pin: true, cidVersion: 0 });
      console.log(`   ✅ Test upload successful! CID: ${result.cid.toString()}`);
      return { success: true, nodeName, apiUrl, cid: result.cid.toString() };
    }

    // Direct HTTP API check
    const vRes = await fetch(`${apiUrl}/api/v0/version`, { method: "POST" });
    const vData = await vRes.json();
    console.log(`   ✅ Connected! IPFS version: ${vData.Version}`);
    const idRes = await fetch(`${apiUrl}/api/v0/id`, { method: "POST" });
    const idData = await idRes.json();
    console.log(`   ✅ Node ID: ${idData.ID.substring(0, 20)}...`);
    const addRes = await fetch(`${apiUrl}/api/v0/add`, { method: "POST", body: `Test file for ${nodeName}` });
    const addData = await addRes.json();
    console.log(`   ✅ Test upload successful! CID: ${addData.Hash}`);
    return { success: true, nodeName, apiUrl, cid: addData.Hash };

    // Test 4: Retrieve file
    const retrieved = await ipfs.cat(result.cid);
    const chunks = [];
    for await (const chunk of retrieved) {
      chunks.push(chunk);
    }
    const content = Buffer.concat(chunks).toString();
    console.log(`   ✅ File retrieval successful! Length: ${content.length} bytes`);

    return {
      success: true,
      nodeName,
      apiUrl,
      cid: result.cid.toString(),
      nodeId: id.id
    };
  } catch (error) {
    console.log(`   ❌ Connection failed: ${error.message}`);
    return {
      success: false,
      nodeName,
      apiUrl,
      error: error.message
    };
  }
}

async function main() {
  console.log("🧪 Testing IPFS Node Connections\n");

  const nodes = [
    { name: "Hospital 1", url: "http://127.0.0.1:5001" },
    { name: "Hospital 2", url: "http://127.0.0.1:5002" },
    { name: "Hospital 3", url: "http://127.0.0.1:5003" },
    { name: "Global Node", url: "http://127.0.0.1:5004" },
  ];

  const results = [];
  for (const node of nodes) {
    const result = await testIPFSConnection(node.url, node.name);
    results.push(result);
  }

  console.log("\n📊 Test Summary:");
  console.log("=".repeat(50));
  const successful = results.filter(r => r.success);
  console.log(`✅ Successful: ${successful.length}/${nodes.length}`);
  successful.forEach(r => {
    console.log(`   ${r.nodeName}: ${r.cid}`);
  });

  const resultsPath = "ipfs_connection_test_results.json";
  fs.writeFileSync(
    resultsPath,
    JSON.stringify({ timestamp: new Date().toISOString(), results }, null, 2)
  );
  console.log(`\n💾 Results saved to: ${resultsPath}`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Fatal error:", error);
    process.exit(1);
  });
