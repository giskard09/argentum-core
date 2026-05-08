// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Votes.sol";
import "@openzeppelin/contracts/token/ERC20/extensions/ERC20Permit.sol";
import "@openzeppelin/contracts/access/Ownable.sol";

/// @notice RAMA governance token — skeleton only, testnet Arbitrum Sepolia
/// @dev Revenue share and distribution are PENDING Legales approval before activation
contract RamaToken is ERC20, ERC20Permit, ERC20Votes, Ownable {
    uint256 public constant MAX_SUPPLY = 100_000_000 ether;

    // Address of the RamaStaking contract — set post-deploy
    address public stakingContract;

    event StakingContractSet(address indexed staking);
    event RevenueDistributed(uint256 amount);

    constructor(address initialOwner)
        ERC20("RAMA", "RAMA")
        ERC20Permit("RAMA")
        Ownable(initialOwner)
    {
        // Founder allocation minted to owner at deploy
        // Full distribution schedule: docs/rfcs/001-agent-vault.md § Path B
        _mint(initialOwner, MAX_SUPPLY);
    }

    /// @notice Set the staking contract address (one-time, owner only)
    function setStakingContract(address _staking) external onlyOwner {
        require(stakingContract == address(0), "already set");
        stakingContract = _staking;
        emit StakingContractSet(_staking);
    }

    /// @notice Distribute ETH revenue to stakers via staking contract
    /// @dev STANDBY — activation condition: >=1 paying client + >=3 months trails
    function distributeRevenue() external {
        require(stakingContract != address(0), "staking not set");
        uint256 balance = address(this).balance;
        require(balance > 0, "no revenue");
        // Forward to staking contract for pro-rata distribution
        (bool ok,) = stakingContract.call{value: balance}("");
        require(ok, "transfer failed");
        emit RevenueDistributed(balance);
    }

    receive() external payable {}

    // ERC20Votes overrides
    function _update(address from, address to, uint256 value)
        internal
        override(ERC20, ERC20Votes)
    {
        super._update(from, to, value);
    }

    function nonces(address owner)
        public
        view
        override(ERC20Permit, Nonces)
        returns (uint256)
    {
        return super.nonces(owner);
    }
}
