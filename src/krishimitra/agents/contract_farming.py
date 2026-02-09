"""
Contract Farming and Buyer Connection System for KrishiMitra Platform

This module implements verified buyer database management, contract opportunity
identification, fair-price validation, and farmer-buyer communication platform.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum
import json
import uuid

import redis
from pydantic import BaseModel, Field, validator
from langchain.tools import BaseTool
from langchain.prompts import PromptTemplate
from langchain_aws import ChatBedrock

from ..core.config import get_settings
from ..models.agricultural_intelligence import GeographicCoordinate, MonetaryAmount

logger = logging.getLogger(__name__)
settings = get_settings()


class BuyerType(str, Enum):
    """Types of buyers"""
    PROCESSOR = "processor"
    EXPORTER = "exporter"
    WHOLESALER = "wholesaler"
    RETAILER = "retailer"
    COOPERATIVE = "cooperative"
    GOVERNMENT = "government"


class ContractStatus(str, Enum):
    """Contract status"""
    DRAFT = "draft"
    PROPOSED = "proposed"
    NEGOTIATING = "negotiating"
    ACCEPTED = "accepted"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VerifiedBuyer(BaseModel):
    """Model for verified buyer information"""
    buyer_id: str = Field(..., description="Unique buyer ID")
    name: str = Field(..., description="Buyer name")
    buyer_type: BuyerType = Field(..., description="Type of buyer")
    location: GeographicCoordinate = Field(..., description="Buyer location")
    address: str = Field(..., description="Physical address")
    contact_phone: str = Field(..., description="Contact phone number")
    contact_email: Optional[str] = Field(None, description="Contact email")
    
    # Verification details
    is_verified: bool = Field(default=False, description="Verification status")
    verification_date: Optional[datetime] = Field(None, description="Date of verification")
    verification_documents: List[str] = Field(default_factory=list, description="Verification document IDs")
    
    # Business details
    commodities_interested: List[str] = Field(..., description="Commodities buyer is interested in")
    minimum_quantity_quintals: float = Field(..., ge=0, description="Minimum quantity required")
    maximum_quantity_quintals: Optional[float] = Field(None, ge=0, description="Maximum quantity capacity")
    payment_terms: str = Field(..., description="Payment terms")
    quality_requirements: Dict[str, Any] = Field(default_factory=dict, description="Quality requirements")
    
    # Ratings and reputation
    rating: Optional[float] = Field(None, ge=0, le=5, description="Buyer rating (0-5)")
    total_contracts: int = Field(default=0, ge=0, description="Total contracts completed")
    successful_contracts: int = Field(default=0, ge=0, description="Successful contracts")
    
    # Operational details
    operating_regions: List[str] = Field(default_factory=list, description="Regions where buyer operates")
    preferred_delivery_locations: List[str] = Field(default_factory=list, description="Preferred delivery locations")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Registration date")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update date")


class ContractOpportunity(BaseModel):
    """Model for contract farming opportunity"""
    opportunity_id: str = Field(..., description="Unique opportunity ID")
    buyer_id: str = Field(..., description="Buyer ID")
    buyer_name: str = Field(..., description="Buyer name")
    
    # Commodity details
    commodity: str = Field(..., description="Commodity name")
    variety: Optional[str] = Field(None, description="Specific variety")
    quantity_quintals: float = Field(..., ge=0, description="Required quantity")
    
    # Pricing
    offered_price_per_quintal: MonetaryAmount = Field(..., description="Offered price")
    price_basis: str = Field(..., description="Price basis (fixed, market-linked, etc.)")
    
    # Contract terms
    contract_duration_months: int = Field(..., ge=1, description="Contract duration")
    delivery_schedule: str = Field(..., description="Delivery schedule")
    payment_terms: str = Field(..., description="Payment terms")
    advance_payment_percent: Optional[float] = Field(None, ge=0, le=100, description="Advance payment percentage")
    
    # Quality requirements
    quality_standards: Dict[str, Any] = Field(default_factory=dict, description="Quality standards")
    rejection_criteria: List[str] = Field(default_factory=list, description="Rejection criteria")
    
    # Location and logistics
    delivery_location: str = Field(..., description="Delivery location")
    transportation_responsibility: str = Field(..., description="Who handles transportation")
    
    # Opportunity details
    valid_until: datetime = Field(..., description="Opportunity validity date")
    target_regions: List[str] = Field(default_factory=list, description="Target regions")
    minimum_land_area_acres: Optional[float] = Field(None, ge=0, description="Minimum land area required")
    
    # Status
    status: str = Field(default="active", description="Opportunity status")
    interested_farmers: List[str] = Field(default_factory=list, description="List of interested farmer IDs")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation date")


class ContractProposal(BaseModel):
    """Model for contract proposal"""
    proposal_id: str = Field(..., description="Unique proposal ID")
    opportunity_id: str = Field(..., description="Related opportunity ID")
    farmer_id: str = Field(..., description="Farmer ID")
    buyer_id: str = Field(..., description="Buyer ID")
    
    # Proposal details
    proposed_quantity_quintals: float = Field(..., ge=0, description="Proposed quantity")
    proposed_price_per_quintal: Optional[MonetaryAmount] = Field(None, description="Counter-offered price")
    farmer_notes: Optional[str] = Field(None, description="Farmer's notes")
    
    # Status
    status: ContractStatus = Field(default=ContractStatus.PROPOSED, description="Proposal status")
    buyer_response: Optional[str] = Field(None, description="Buyer's response")
    
    # Negotiation history
    negotiation_history: List[Dict[str, Any]] = Field(default_factory=list, description="Negotiation messages")
    
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Proposal date")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update")


class ContractFarmingSystem:
    """System for managing contract farming and buyer connections"""
    
    def __init__(self):
        self.redis_client = redis.Redis(
            host='localhost',
            port=6379,
            decode_responses=True
        )
        
        # Initialize LangChain for contract analysis
        self.llm = ChatBedrock(
            model_id=settings.bedrock_model_id,
            region_name=settings.bedrock_region
        )
        
        # Fair price validation threshold (percentage)
        self.fair_price_threshold = 0.85  # Offered price should be at least 85% of market price
    
    async def register_buyer(self, buyer_data: Dict[str, Any]) -> VerifiedBuyer:
        """Register a new buyer in the system"""
        try:
            buyer_id = f"buyer_{uuid.uuid4().hex[:12]}"
            
            buyer = VerifiedBuyer(
                buyer_id=buyer_id,
                **buyer_data
            )
            
            # Store in Redis
            buyer_key = f"buyer:{buyer_id}"
            self.redis_client.setex(
                buyer_key,
                365 * 24 * 3600,  # 1 year expiry
                buyer.json()
            )
            
            # Add to buyers index
            self.redis_client.sadd("buyers:all", buyer_id)
            
            # Index by commodities
            for commodity in buyer.commodities_interested:
                self.redis_client.sadd(f"buyers:commodity:{commodity.lower()}", buyer_id)
            
            # Index by regions
            for region in buyer.operating_regions:
                self.redis_client.sadd(f"buyers:region:{region.lower()}", buyer_id)
            
            logger.info(f"Registered new buyer: {buyer_id}")
            return buyer
            
        except Exception as e:
            logger.error(f"Error registering buyer: {e}")
            raise
    
    async def get_buyer(self, buyer_id: str) -> Optional[VerifiedBuyer]:
        """Get buyer information"""
        try:
            buyer_key = f"buyer:{buyer_id}"
            buyer_data = self.redis_client.get(buyer_key)
            
            if buyer_data:
                return VerifiedBuyer.parse_raw(buyer_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting buyer: {e}")
            return None
    
    async def find_buyers_for_commodity(
        self,
        commodity: str,
        region: Optional[str] = None,
        minimum_quantity: Optional[float] = None
    ) -> List[VerifiedBuyer]:
        """Find verified buyers for a specific commodity"""
        try:
            # Get buyers interested in this commodity
            buyer_ids = self.redis_client.smembers(f"buyers:commodity:{commodity.lower()}")
            
            buyers = []
            for buyer_id in buyer_ids:
                buyer = await self.get_buyer(buyer_id)
                
                if not buyer or not buyer.is_verified:
                    continue
                
                # Filter by region if specified
                if region and region.lower() not in [r.lower() for r in buyer.operating_regions]:
                    continue
                
                # Filter by minimum quantity if specified
                if minimum_quantity and buyer.minimum_quantity_quintals > minimum_quantity:
                    continue
                
                buyers.append(buyer)
            
            # Sort by rating
            buyers.sort(key=lambda x: x.rating or 0, reverse=True)
            
            logger.info(f"Found {len(buyers)} buyers for {commodity}")
            return buyers
            
        except Exception as e:
            logger.error(f"Error finding buyers: {e}")
            return []
    
    async def create_contract_opportunity(
        self,
        buyer_id: str,
        opportunity_data: Dict[str, Any]
    ) -> ContractOpportunity:
        """Create a new contract farming opportunity"""
        try:
            # Verify buyer exists
            buyer = await self.get_buyer(buyer_id)
            if not buyer:
                raise ValueError(f"Buyer {buyer_id} not found")
            
            opportunity_id = f"opp_{uuid.uuid4().hex[:12]}"
            
            opportunity = ContractOpportunity(
                opportunity_id=opportunity_id,
                buyer_id=buyer_id,
                buyer_name=buyer.name,
                **opportunity_data
            )
            
            # Store in Redis
            opp_key = f"opportunity:{opportunity_id}"
            self.redis_client.setex(
                opp_key,
                90 * 24 * 3600,  # 90 days expiry
                opportunity.json()
            )
            
            # Add to opportunities index
            self.redis_client.sadd("opportunities:active", opportunity_id)
            
            # Index by commodity
            self.redis_client.sadd(
                f"opportunities:commodity:{opportunity.commodity.lower()}",
                opportunity_id
            )
            
            # Index by regions
            for region in opportunity.target_regions:
                self.redis_client.sadd(
                    f"opportunities:region:{region.lower()}",
                    opportunity_id
                )
            
            logger.info(f"Created contract opportunity: {opportunity_id}")
            return opportunity
            
        except Exception as e:
            logger.error(f"Error creating contract opportunity: {e}")
            raise
    
    async def get_contract_opportunity(self, opportunity_id: str) -> Optional[ContractOpportunity]:
        """Get contract opportunity details"""
        try:
            opp_key = f"opportunity:{opportunity_id}"
            opp_data = self.redis_client.get(opp_key)
            
            if opp_data:
                return ContractOpportunity.parse_raw(opp_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting contract opportunity: {e}")
            return None
    
    async def find_contract_opportunities(
        self,
        commodity: Optional[str] = None,
        region: Optional[str] = None,
        farmer_location: Optional[GeographicCoordinate] = None
    ) -> List[ContractOpportunity]:
        """Find contract opportunities matching criteria"""
        try:
            opportunity_ids = set()
            
            if commodity:
                # Get opportunities for specific commodity
                opp_ids = self.redis_client.smembers(f"opportunities:commodity:{commodity.lower()}")
                opportunity_ids.update(opp_ids)
            else:
                # Get all active opportunities
                opportunity_ids = self.redis_client.smembers("opportunities:active")
            
            opportunities = []
            for opp_id in opportunity_ids:
                opportunity = await self.get_contract_opportunity(opp_id)
                
                if not opportunity or opportunity.status != "active":
                    continue
                
                # Check if opportunity is still valid
                if opportunity.valid_until < datetime.utcnow():
                    continue
                
                # Filter by region if specified
                if region and region.lower() not in [r.lower() for r in opportunity.target_regions]:
                    continue
                
                opportunities.append(opportunity)
            
            # Sort by offered price (descending)
            opportunities.sort(
                key=lambda x: x.offered_price_per_quintal.amount,
                reverse=True
            )
            
            logger.info(f"Found {len(opportunities)} contract opportunities")
            return opportunities
            
        except Exception as e:
            logger.error(f"Error finding contract opportunities: {e}")
            return []
    
    async def validate_fair_price(
        self,
        commodity: str,
        offered_price: float,
        current_market_prices: List[float]
    ) -> Dict[str, Any]:
        """Validate if offered price is fair compared to market prices"""
        try:
            if not current_market_prices:
                return {
                    "is_fair": None,
                    "message": "No market price data available for comparison"
                }
            
            avg_market_price = sum(current_market_prices) / len(current_market_prices)
            price_ratio = offered_price / avg_market_price if avg_market_price > 0 else 0
            
            is_fair = price_ratio >= self.fair_price_threshold
            
            validation_result = {
                "is_fair": is_fair,
                "offered_price": offered_price,
                "average_market_price": avg_market_price,
                "price_ratio": price_ratio,
                "threshold": self.fair_price_threshold,
                "price_difference_percent": (price_ratio - 1) * 100
            }
            
            if is_fair:
                if price_ratio >= 1.0:
                    validation_result["message"] = f"Excellent price - {((price_ratio - 1) * 100):.1f}% above market average"
                else:
                    validation_result["message"] = f"Fair price - {((1 - price_ratio) * 100):.1f}% below market average but within acceptable range"
            else:
                validation_result["message"] = f"Price may be too low - {((1 - price_ratio) * 100):.1f}% below market average"
                validation_result["recommendation"] = "Consider negotiating for a better price"
            
            return validation_result
            
        except Exception as e:
            logger.error(f"Error validating fair price: {e}")
            return {
                "is_fair": None,
                "message": f"Error validating price: {str(e)}"
            }
    
    async def create_contract_proposal(
        self,
        farmer_id: str,
        opportunity_id: str,
        proposal_data: Dict[str, Any]
    ) -> ContractProposal:
        """Create a contract proposal from farmer to buyer"""
        try:
            # Verify opportunity exists
            opportunity = await self.get_contract_opportunity(opportunity_id)
            if not opportunity:
                raise ValueError(f"Opportunity {opportunity_id} not found")
            
            proposal_id = f"prop_{uuid.uuid4().hex[:12]}"
            
            proposal = ContractProposal(
                proposal_id=proposal_id,
                opportunity_id=opportunity_id,
                farmer_id=farmer_id,
                buyer_id=opportunity.buyer_id,
                **proposal_data
            )
            
            # Store in Redis
            prop_key = f"proposal:{proposal_id}"
            self.redis_client.setex(
                prop_key,
                90 * 24 * 3600,  # 90 days expiry
                proposal.json()
            )
            
            # Add to farmer's proposals
            self.redis_client.sadd(f"farmer_proposals:{farmer_id}", proposal_id)
            
            # Add to buyer's proposals
            self.redis_client.sadd(f"buyer_proposals:{opportunity.buyer_id}", proposal_id)
            
            # Update opportunity with interested farmer
            if farmer_id not in opportunity.interested_farmers:
                opportunity.interested_farmers.append(farmer_id)
                opp_key = f"opportunity:{opportunity_id}"
                self.redis_client.setex(
                    opp_key,
                    90 * 24 * 3600,
                    opportunity.json()
                )
            
            logger.info(f"Created contract proposal: {proposal_id}")
            return proposal
            
        except Exception as e:
            logger.error(f"Error creating contract proposal: {e}")
            raise
    
    async def get_contract_proposal(self, proposal_id: str) -> Optional[ContractProposal]:
        """Get contract proposal details"""
        try:
            prop_key = f"proposal:{proposal_id}"
            prop_data = self.redis_client.get(prop_key)
            
            if prop_data:
                return ContractProposal.parse_raw(prop_data)
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting contract proposal: {e}")
            return None
    
    async def add_negotiation_message(
        self,
        proposal_id: str,
        sender: str,
        message: str
    ) -> bool:
        """Add a negotiation message to a proposal"""
        try:
            proposal = await self.get_contract_proposal(proposal_id)
            if not proposal:
                return False
            
            negotiation_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "sender": sender,
                "message": message
            }
            
            proposal.negotiation_history.append(negotiation_entry)
            proposal.updated_at = datetime.utcnow()
            
            # Update in Redis
            prop_key = f"proposal:{proposal_id}"
            self.redis_client.setex(
                prop_key,
                90 * 24 * 3600,
                proposal.json()
            )
            
            logger.info(f"Added negotiation message to proposal {proposal_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding negotiation message: {e}")
            return False
    
    async def update_proposal_status(
        self,
        proposal_id: str,
        new_status: ContractStatus,
        response_message: Optional[str] = None
    ) -> bool:
        """Update contract proposal status"""
        try:
            proposal = await self.get_contract_proposal(proposal_id)
            if not proposal:
                return False
            
            proposal.status = new_status
            proposal.updated_at = datetime.utcnow()
            
            if response_message:
                proposal.buyer_response = response_message
            
            # Update in Redis
            prop_key = f"proposal:{proposal_id}"
            self.redis_client.setex(
                prop_key,
                90 * 24 * 3600,
                proposal.json()
            )
            
            # If accepted, update buyer statistics
            if new_status == ContractStatus.ACCEPTED:
                buyer = await self.get_buyer(proposal.buyer_id)
                if buyer:
                    buyer.total_contracts += 1
                    buyer_key = f"buyer:{proposal.buyer_id}"
                    self.redis_client.setex(
                        buyer_key,
                        365 * 24 * 3600,
                        buyer.json()
                    )
            
            logger.info(f"Updated proposal {proposal_id} status to {new_status}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating proposal status: {e}")
            return False
    
    async def get_farmer_proposals(self, farmer_id: str) -> List[ContractProposal]:
        """Get all proposals for a farmer"""
        try:
            proposal_ids = self.redis_client.smembers(f"farmer_proposals:{farmer_id}")
            
            proposals = []
            for prop_id in proposal_ids:
                proposal = await self.get_contract_proposal(prop_id)
                if proposal:
                    proposals.append(proposal)
            
            # Sort by creation date (newest first)
            proposals.sort(key=lambda x: x.created_at, reverse=True)
            
            return proposals
            
        except Exception as e:
            logger.error(f"Error getting farmer proposals: {e}")
            return []
    
    async def analyze_contract_terms(
        self,
        opportunity: ContractOpportunity,
        farmer_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze contract terms using LLM to provide recommendations"""
        try:
            prompt_template = PromptTemplate(
                input_variables=["opportunity", "farmer_context"],
                template="""
                Analyze the following contract farming opportunity and provide recommendations for the farmer:
                
                Contract Details:
                - Commodity: {opportunity[commodity]}
                - Quantity Required: {opportunity[quantity_quintals]} quintals
                - Offered Price: ₹{opportunity[offered_price_per_quintal]} per quintal
                - Contract Duration: {opportunity[contract_duration_months]} months
                - Payment Terms: {opportunity[payment_terms]}
                - Delivery Location: {opportunity[delivery_location]}
                
                Farmer Context:
                - Current Market Price: ₹{farmer_context[current_market_price]} per quintal
                - Farmer's Capacity: {farmer_context[farmer_capacity]} quintals
                - Distance to Delivery: {farmer_context[distance_km]} km
                
                Provide a brief analysis covering:
                1. Price competitiveness
                2. Risk assessment
                3. Key recommendations
                4. Potential concerns
                
                Keep the response concise and farmer-friendly.
                """
            )
            
            # Prepare opportunity data
            opp_data = {
                "commodity": opportunity.commodity,
                "quantity_quintals": opportunity.quantity_quintals,
                "offered_price_per_quintal": opportunity.offered_price_per_quintal.amount,
                "contract_duration_months": opportunity.contract_duration_months,
                "payment_terms": opportunity.payment_terms,
                "delivery_location": opportunity.delivery_location
            }
            
            # Generate analysis
            prompt = prompt_template.format(
                opportunity=opp_data,
                farmer_context=farmer_context
            )
            
            response = await self.llm.ainvoke(prompt)
            
            return {
                "analysis": response.content,
                "opportunity_id": opportunity.opportunity_id,
                "generated_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing contract terms: {e}")
            return {
                "analysis": "Unable to generate analysis at this time",
                "error": str(e)
            }


class ContractFarmingTool(BaseTool):
    """LangChain tool for contract farming operations"""
    
    name: str = "contract_farming"
    description: str = "Find contract farming opportunities and connect farmers with verified buyers"
    
    def _run(self, commodity: str, region: str = None) -> str:
        """Run the contract farming tool"""
        import asyncio
        
        async def find_opportunities():
            system = ContractFarmingSystem()
            opportunities = await system.find_contract_opportunities(
                commodity=commodity,
                region=region
            )
            
            if not opportunities:
                return f"No contract farming opportunities found for {commodity}"
            
            response = f"Found {len(opportunities)} contract opportunities for {commodity}:\n\n"
            
            for opp in opportunities[:3]:  # Show top 3
                response += f"- {opp.buyer_name}: ₹{opp.offered_price_per_quintal.amount}/quintal for {opp.quantity_quintals} quintals\n"
                response += f"  Payment: {opp.payment_terms}\n"
                response += f"  Valid until: {opp.valid_until.strftime('%Y-%m-%d')}\n\n"
            
            return response
        
        return asyncio.run(find_opportunities())
    
    async def _arun(self, commodity: str, region: str = None) -> str:
        """Async version of the tool"""
        system = ContractFarmingSystem()
        opportunities = await system.find_contract_opportunities(
            commodity=commodity,
            region=region
        )
        
        if not opportunities:
            return f"No contract farming opportunities found for {commodity}"
        
        response = f"Found {len(opportunities)} contract opportunities for {commodity}:\n\n"
        
        for opp in opportunities[:3]:  # Show top 3
            response += f"- {opp.buyer_name}: ₹{opp.offered_price_per_quintal.amount}/quintal for {opp.quantity_quintals} quintals\n"
            response += f"  Payment: {opp.payment_terms}\n"
            response += f"  Valid until: {opp.valid_until.strftime('%Y-%m-%d')}\n\n"
        
        return response
