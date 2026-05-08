// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/IERC20.sol";
import "@openzeppelin/contracts/token/ERC20/utils/SafeERC20.sol";
import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

interface IArgentumKarma {
    function getKarma(string calldata agentId) external view returns (uint256);
}

/// @notice RAMA staking — skeleton only, testnet Arbitrum Sepolia
/// @dev Revenue distribution PENDING Legales. Fee discounts PENDING integration.
contract RamaStaking is Ownable, ReentrancyGuard {
    using SafeERC20 for IERC20;

    IERC20 public immutable ramaToken;
    IArgentumKarma public karmaRegistry;

    // Discount tiers: staked balance thresholds (in RAMA wei)
    uint256 public constant TIER_LOW    =   1_000 ether;
    uint256 public constant TIER_MEDIUM =  10_000 ether;
    uint256 public constant TIER_HIGH   = 100_000 ether;

    struct StakeInfo {
        uint256 amount;
        uint256 rewardDebt;
    }

    mapping(address => StakeInfo) public stakes;
    uint256 public totalStaked;

    // Accumulated reward per token (scaled 1e18)
    uint256 public accRewardPerToken;
    uint256 public pendingRevenue;

    event Staked(address indexed user, uint256 amount);
    event Unstaked(address indexed user, uint256 amount);
    event RewardClaimed(address indexed user, uint256 reward);
    event RevenueReceived(uint256 amount);

    constructor(address _ramaToken, address _karmaRegistry, address _owner)
        Ownable(_owner)
    {
        ramaToken = IERC20(_ramaToken);
        karmaRegistry = IArgentumKarma(_karmaRegistry);
    }

    /// @notice Stake RAMA tokens
    function stake(uint256 amount) external nonReentrant {
        _claimFor(msg.sender);
        ramaToken.safeTransferFrom(msg.sender, address(this), amount);
        stakes[msg.sender].amount += amount;
        totalStaked += amount;
        emit Staked(msg.sender, amount);
    }

    /// @notice Unstake RAMA tokens
    function unstake(uint256 amount) external nonReentrant {
        require(stakes[msg.sender].amount >= amount, "insufficient stake");
        _claimFor(msg.sender);
        stakes[msg.sender].amount -= amount;
        totalStaked -= amount;
        ramaToken.safeTransfer(msg.sender, amount);
        emit Unstaked(msg.sender, amount);
    }

    /// @notice Claim accumulated rewards
    function claimRewards() external nonReentrant {
        _claimFor(msg.sender);
    }

    /// @notice Fee discount tier for an address (0 = none, 1 = low, 2 = medium, 3 = high)
    function feeDiscountTier(address user) external view returns (uint8) {
        uint256 staked = stakes[user].amount;
        if (staked >= TIER_HIGH)   return 3;
        if (staked >= TIER_MEDIUM) return 2;
        if (staked >= TIER_LOW)    return 1;
        return 0;
    }

    /// @notice Combined score: karma + staking tier (used by Mycelium for pricing)
    function agentScore(address user, string calldata agentId) external view returns (uint256) {
        uint256 karma = karmaRegistry.getKarma(agentId);
        uint8 tier = this.feeDiscountTier(user);
        return karma + uint256(tier) * 10;
    }

    // Receive ETH revenue from RamaToken.distributeRevenue()
    receive() external payable {
        if (totalStaked > 0) {
            accRewardPerToken += (msg.value * 1e18) / totalStaked;
        }
        pendingRevenue += msg.value;
        emit RevenueReceived(msg.value);
    }

    function _claimFor(address user) internal {
        uint256 staked = stakes[user].amount;
        if (staked == 0) {
            stakes[user].rewardDebt = accRewardPerToken;
            return;
        }
        uint256 pending = (staked * (accRewardPerToken - stakes[user].rewardDebt)) / 1e18;
        stakes[user].rewardDebt = accRewardPerToken;
        if (pending > 0) {
            (bool ok,) = user.call{value: pending}("");
            require(ok, "reward transfer failed");
            emit RewardClaimed(user, pending);
        }
    }
}
