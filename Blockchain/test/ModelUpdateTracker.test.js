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

    // Cannot re-publish global model for same round
    await expect(
      tracker.connect(owner).publishGlobalModel(globalCid, globalHash)
    ).to.be.revertedWith("Not enough hospitals");
  });

  it("Should revert on constructor with quorum = 0", async function () {
    const ModelUpdateTracker = await hre.ethers.getContractFactory("ModelUpdateTracker");
    await expect(ModelUpdateTracker.deploy(0)).to.be.revertedWith("quorum=0");
  });

  it("Should reject empty CID and zero hash on submitLocalModel", async function () {
    await tracker.registerHospital(hospital1.address);
    const validHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("weights"));
    const zeroHash = hre.ethers.ZeroHash;

    await expect(
      tracker.connect(hospital1).submitLocalModel("", validHash)
    ).to.be.revertedWith("empty cid");

    await expect(
      tracker.connect(hospital1).submitLocalModel("QmValidCid", zeroHash)
    ).to.be.revertedWith("empty hash");
  });

  it("Should reject zero address on setAggregator and emit AggregatorChanged", async function () {
    await expect(
      tracker.connect(owner).setAggregator(hre.ethers.ZeroAddress)
    ).to.be.revertedWith("zero addr");

    await expect(tracker.connect(owner).setAggregator(hospital1.address))
      .to.emit(tracker, "AggregatorChanged")
      .withArgs(owner.address, hospital1.address);
  });

  it("Should allow updating quorum and emit QuorumChanged", async function () {
    await expect(
      tracker.connect(owner).setRequiredSubmissions(0)
    ).to.be.revertedWith("quorum=0");

    await expect(tracker.connect(owner).setRequiredSubmissions(5))
      .to.emit(tracker, "QuorumChanged")
      .withArgs(REQUIRED_SUBMISSIONS, 5);

    expect(await tracker.requiredSubmissions()).to.equal(5);
  });

  it("Should revoke a hospital and prevent further submissions", async function () {
    await tracker.registerHospital(hospital1.address);
    expect((await tracker.hospitalContributions(hospital1.address)).isRegistered).to.be.true;

    await expect(tracker.connect(owner).revokeHospital(hospital1.address))
      .to.emit(tracker, "HospitalRevoked")
      .withArgs(hospital1.address);

    expect((await tracker.hospitalContributions(hospital1.address)).isRegistered).to.be.false;

    const dummyCid = "QmTestHospitalLocalModel1";
    const dummyHash = hre.ethers.keccak256(hre.ethers.toUtf8Bytes("model_bytes_1"));
    await expect(
      tracker.connect(hospital1).submitLocalModel(dummyCid, dummyHash)
    ).to.be.revertedWith("Not hospital");
  });

  it("Should dynamically adapt quorum when a hospital is revoked to prevent training deadlock", async function () {
    await tracker.registerHospital(hospital1.address);
    await tracker.registerHospital(hospital2.address);
    await tracker.registerHospital(hospital3.address);

    expect(await tracker.activeHospitalCount()).to.equal(3);
    expect(await tracker.requiredSubmissions()).to.equal(3);

    // Revoke hospital 3 -> active count drops to 2, quorum automatically adapts to 2
    await expect(tracker.connect(owner).revokeHospital(hospital3.address))
      .to.emit(tracker, "QuorumChanged")
      .withArgs(3, 2);

    expect(await tracker.activeHospitalCount()).to.equal(2);
    expect(await tracker.requiredSubmissions()).to.equal(2);

    const activeList = await tracker.getActiveHospitals();
    expect(activeList.length).to.equal(2);
    expect(activeList).to.include(hospital1.address);
    expect(activeList).to.include(hospital2.address);
    expect(activeList).to.not.include(hospital3.address);

    // Now hospitals 1 and 2 submit their models
    await tracker.connect(hospital1).submitLocalModel(
      "QmH1",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("h1"))
    );
    await tracker.connect(hospital2).submitLocalModel(
      "QmH2",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("h2"))
    );

    // Global model can now be published without deadlocking
    await expect(tracker.connect(owner).publishGlobalModel(
      "QmGlobalRound1",
      hre.ethers.keccak256(hre.ethers.toUtf8Bytes("global"))
    )).to.emit(tracker, "RoundAdvanced").withArgs(2);

    expect(await tracker.currentRound()).to.equal(2);
  });
});
