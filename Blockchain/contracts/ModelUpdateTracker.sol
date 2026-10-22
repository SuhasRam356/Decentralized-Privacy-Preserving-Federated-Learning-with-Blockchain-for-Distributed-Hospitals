// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract ModelUpdateTracker {

    // ---------------- ROLES ----------------
    address public owner;
    address public aggregator; // global model publisher (global node)

    // ---------------- CONFIG ----------------
    uint256 public requiredSubmissions; // min hospitals per round
    uint256 public currentRound;

    bool public paused;

    // ---------------- STRUCTS ----------------
    struct ModelPointer {
        string cid;        // IPFS CID
        bytes32 fileHash;  // sha256(model bytes) off-chain
        uint256 timestamp;
        address submitter;
    }

    struct HospitalContribution {
        bool isRegistered;
        uint256 totalSubmissions;
        uint256 lastRound;
    }

    // ---------------- STORAGE ----------------

    // round => hospital => local model
    mapping(uint256 => mapping(address => ModelPointer)) private localModels;

    // round => hospitals submitted
    mapping(uint256 => address[]) private roundHospitals;
    mapping(uint256 => mapping(address => bool)) public hasSubmitted;

    // round => global model
    mapping(uint256 => ModelPointer) private globalModels;

    // hospitals
    mapping(address => HospitalContribution) public hospitalContributions;
    address[] public registeredHospitals;

    // ---------------- EVENTS ----------------
    event HospitalRegistered(address hospital);
    event HospitalRevoked(address indexed hospital);
    event AggregatorChanged(address indexed oldAggregator, address indexed newAggregator);
    event QuorumChanged(uint256 oldQuorum, uint256 newQuorum);
    event LocalModelSubmitted(uint256 round, address hospital, string cid);
    event GlobalModelPublished(uint256 round, string cid);
    event RoundAdvanced(uint256 newRound);

    // ---------------- MODIFIERS ----------------
    modifier onlyOwner() {
        require(msg.sender == owner, "Only owner");
        _;
    }

    modifier onlyAggregator() {
        require(msg.sender == aggregator, "Only aggregator");
        _;
    }

    modifier onlyHospital() {
        require(hospitalContributions[msg.sender].isRegistered, "Not hospital");
        _;
    }

    modifier whenNotPaused() {
        require(!paused, "Paused");
        _;
    }

    // ---------------- CONSTRUCTOR ----------------
    constructor(uint256 _requiredSubmissions) {
        require(_requiredSubmissions > 0, "quorum=0");
        owner = msg.sender;
        aggregator = msg.sender;
        requiredSubmissions = _requiredSubmissions;
        currentRound = 1;
    }

    // ---------------- ADMIN ----------------
    function registerHospital(address h) external onlyOwner whenNotPaused {
        require(h != address(0), "zero addr");
        require(!hospitalContributions[h].isRegistered, "Already registered");

        hospitalContributions[h] = HospitalContribution({
            isRegistered: true,
            totalSubmissions: 0,
            lastRound: 0
        });

        registeredHospitals.push(h);
        emit HospitalRegistered(h);
    }

    function revokeHospital(address h) external onlyOwner {
        require(hospitalContributions[h].isRegistered, "Not registered");
        hospitalContributions[h].isRegistered = false;
        emit HospitalRevoked(h);
    }

    function setRequiredSubmissions(uint256 n) external onlyOwner {
        require(n > 0, "quorum=0");
        emit QuorumChanged(requiredSubmissions, n);
        requiredSubmissions = n;
    }

    function setAggregator(address a) external onlyOwner {
        require(a != address(0), "zero addr");
        emit AggregatorChanged(aggregator, a);
        aggregator = a;
    }

    function pause() external onlyOwner {
        paused = true;
    }

    function unpause() external onlyOwner {
        paused = false;
    }

    // ---------------- HOSPITAL ----------------
    function submitLocalModel(
        string calldata cid,
        bytes32 fileHash
    )
        external
        onlyHospital
        whenNotPaused
    {
        require(bytes(cid).length > 0, "empty cid");
        require(fileHash != bytes32(0), "empty hash");
        require(!hasSubmitted[currentRound][msg.sender], "Already submitted");

        localModels[currentRound][msg.sender] = ModelPointer({
            cid: cid,
            fileHash: fileHash,
            timestamp: block.timestamp,
            submitter: msg.sender
        });

        hasSubmitted[currentRound][msg.sender] = true;
        roundHospitals[currentRound].push(msg.sender);

        hospitalContributions[msg.sender].totalSubmissions++;
        hospitalContributions[msg.sender].lastRound = currentRound;

        emit LocalModelSubmitted(currentRound, msg.sender, cid);
    }

    // ---------------- AGGREGATOR ----------------
    function publishGlobalModel(
        string calldata cid,
        bytes32 fileHash
    )
        external
        onlyAggregator
        whenNotPaused
    {
        require(bytes(cid).length > 0, "empty cid");
        require(fileHash != bytes32(0), "empty hash");
        require(bytes(globalModels[currentRound].cid).length == 0, "already published");
        require(
            roundHospitals[currentRound].length >= requiredSubmissions,
            "Not enough hospitals"
        );

        globalModels[currentRound] = ModelPointer({
            cid: cid,
            fileHash: fileHash,
            timestamp: block.timestamp,
            submitter: msg.sender
        });

        emit GlobalModelPublished(currentRound, cid);

        currentRound++;
        emit RoundAdvanced(currentRound);
    }

    // ---------------- READ ----------------
    function getLocalModel(uint256 round, address hospital)
        external
        view
        returns (ModelPointer memory)
    {
        return localModels[round][hospital];
    }

    function getGlobalModel(uint256 round)
        external
        view
        returns (ModelPointer memory)
    {
        return globalModels[round];
    }

    function getRoundHospitals(uint256 round)
        external
        view
        returns (address[] memory)
    {
        return roundHospitals[round];
    }
}
