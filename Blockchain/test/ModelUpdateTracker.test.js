const { expect } = require("chai");
const hre = require("hardhat");

describe("ModelUpdateTracker & Federated Learning Lifecycle", function () {
  let tracker;
  let owner, hospital1, hospital2, hospital3, outsider;
  const REQUIRED_SUBMISSIONS = 3;

  beforeEach(async function () {
    [owner, hospital1, hospital2, hospital3, outsider] = await hre.ethers.getSigners();
    const ModelUpdateTracker = await hre.ethers.getContractFactory("ModelUpdateTracker");
    tracker = await ModelUpdateTracker.deploy(REQUIRED_SUBMISSIONS);
    await tracker.waitForDeployment();
  });

  it("Should initialize with correct configuration", async function () {
    expect(await tracker.owner()).to.equal(owner.address);
    expect(await tracker.aggregator()).to.equal(owner.address);
    expect(await tracker.requiredSubmissions()).to.equal(REQUIRED_SUBMISSIONS);
    expect(await tracker.currentRound()).to.equal(1);
  });

  it("Should register hospitals and prevent duplicate registration", async function () {
    await tracker.registerHospital(hospital1.address);
    await tracker.registerHospital(hospital2.address);
    await tracker.registerHospital(hospital3.address);

    const contrib1 = await tracker.hospitalContributions(hospital1.address);
    expect(contrib1.isRegistered).to.be.true;

    await expect(
      tracker.registerHospital(hospital1.address)
    ).to.be.revertedWith("Already registered");
  });

  it("Should prevent unregistered nodes from submitting models", async function () {
    const dummyCid = "QmTestHospitalLocalModel1";
    const dummyHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("model_bytes_1"));

    await expect(
      tracker.connect(outsider).submitLocalModel(dummyCid, dummyHash)
    ).to.be.revertedWith("Not hospital");
  });

  it("Should accept local model submissions from registered hospitals", async function () {
    await tracker.registerHospital(hospital1.address);
    await tracker.registerHospital(hospital2.address);
    await tracker.registerHospital(hospital3.address);

    const cid1 = "QmHospital1Round1CID";
    const hash1 = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("hospital1_weights_round1"));

    await expect(tracker.connect(hospital1).submitLocalModel(cid1, hash1))
      .to.emit(tracker, "LocalModelSubmitted")
      .withArgs(1, hospital1.address, cid1);

    expect(await tracker.hasSubmitted(1, hospital1.address)).to.be.true;
    expect(await tracker.hasSubmitted(1, hospital2.address)).to.be.false;

    // Submitting again in same round should fail
    await expect(
      tracker.connect(hospital1).submitLocalModel(cid1, hash1)
    ).to.be.revertedWith("Already submitted");
  });

  it("Should complete round when required hospitals submit and publish global model", async function () {
    await tracker.registerHospital(hospital1.address);
    await tracker.registerHospital(hospital2.address);
    await tracker.registerHospital(hospital3.address);

    await tracker.connect(hospital1).submitLocalModel(
      "QmH1",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("h1"))
    );
    await tracker.connect(hospital2).submitLocalModel(
      "QmH2",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("h2"))
    );
    await tracker.connect(hospital3).submitLocalModel(
      "QmH3",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("h3"))
    );

    const roundHospitals = await tracker.getRoundHospitals(1);
    expect(roundHospitals.length).to.equal(3);

    // Publishing global model
    const globalCid = "QmGlobalModelRound1Aggregated";
    const globalHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("global_model_round1"));

    await expect(tracker.connect(owner).publishGlobalModel(globalCid, globalHash))
      .to.emit(tracker, "GlobalModelPublished")
      .withArgs(1, globalCid)
      .and.to.emit(tracker, "RoundAdvanced")
      .withArgs(2);

    expect(await tracker.currentRound()).to.equal(2);

    const globalModelInfo = await tracker.getGlobalModel(1);
    expect(globalModelInfo.cid).to.equal(globalCid);
    expect(globalModelInfo.fileHash).to.equal(globalHash);
  });
});
