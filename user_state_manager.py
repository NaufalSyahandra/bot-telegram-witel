import logging
import time
from typing import Dict, List, Optional
from constants import UserState, KendalaType, UserRole

logger = logging.getLogger(__name__)


class UserStateManager:
    """User state management class with registration system"""

    def __init__(self):
        self.user_states: Dict[int, Dict] = {}
        self.registered_users: Dict[str, Dict] = {}  # NIK -> user data
        self.pending_registrations: List[Dict] = []  # List of pending registrations
        # Removed processed_registrations to allow re-registration
        self.admins: List[str] = []  # List of admin NIKs
        self.owner_user_id: Optional[int] = None  # Set this in config

    def set_owner(self, user_id: int):
        """Set owner user ID"""
        self.owner_user_id = user_id
        logger.info(f"Owner set to user_id: {user_id}")

    def is_owner(self, user_id: int) -> bool:
        """Check if user is owner"""
        return user_id == self.owner_user_id

    def is_admin(self, user_id: int) -> bool:
        """Check if user is admin"""
        if self.is_owner(user_id):
            return True
        
        # Check if user_id corresponds to an admin NIK
        for nik, user_data in self.registered_users.items():
            if user_data.get('user_id') == user_id and nik in self.admins:
                return True
        return False

    def add_admin(self, nik: str) -> bool:
        """Add admin by NIK"""
        if nik in self.admins:
            return False
        
        # Check if NIK exists in registered users
        if nik in self.registered_users:
            self.admins.append(nik)
            logger.info(f"Added admin: {nik}")
            return True
        return False

    def remove_admin(self, nik: str) -> bool:
        """Remove admin by NIK"""
        if nik in self.admins:
            self.admins.remove(nik)
            logger.info(f"Removed admin: {nik}")
            return True
        return False

    def remove_user(self, nik: str) -> bool:
        """Remove user completely (owner and admin can do this)"""
        if nik in self.registered_users:
            # Remove from admins if they're admin
            if nik in self.admins:
                self.admins.remove(nik)
            
            # Get user_id before removing
            user_data = self.registered_users[nik]
            user_id = user_data.get('user_id')
            
            # Remove from registered users
            del self.registered_users[nik]
            
            # Reset user state to unregistered
            if user_id:
                self.set_user_state(user_id, UserState.UNREGISTERED)
            
            logger.info(f"Removed user: {nik}")
            return True
        return False

    def register_user(self, user_id: int, nik: str, username: str = None) -> str:
        """Register new user with NIK"""
        # Validate NIK format (6-8 digits)
        if not nik.isdigit() or not (6 <= len(nik) <= 8):
            return "invalid_nik"
        
        # Check if NIK already registered
        if nik in self.registered_users:
            return "already_registered"
        
        # Check if already in pending
        for pending in self.pending_registrations:
            if pending['nik'] == nik:
                return "already_pending"
        
        # Clear any previous rejection status for this user
        if user_id in self.user_states and self.user_states[user_id]['state'] == UserState.REJECTED:
            # Allow re-registration by clearing the state
            del self.user_states[user_id]
        
        # Add to pending registrations
        registration_data = {
            'nik': nik,
            'user_id': user_id,
            'username': username,
            'timestamp': time.time()
        }
        
        self.pending_registrations.append(registration_data)
        logger.info(f"User {user_id} registered with NIK {nik}, pending approval")
        return "success"

    def approve_registration(self, nik: str, approved_by_user_id: int) -> Dict:
        """Approve user registration and return status info"""
        # Find in pending registrations
        registration = None
        for pending in self.pending_registrations:
            if pending['nik'] == nik:
                registration = pending
                break
        
        if not registration:
            return {"success": False, "reason": "not_found"}
        
        # Move to registered users
        self.registered_users[nik] = {
            'user_id': registration['user_id'],
            'username': registration['username'],
            'role': UserRole.EMPLOYEE,
            'status': 'approved',
            'approved_by': approved_by_user_id,
            'approved_at': time.time(),
            'created_at': registration['timestamp']
        }
        
        # Get approver details
        approver_role = "owner" if self.is_owner(approved_by_user_id) else "admin"
        approver_nik = self.get_user_nik(approved_by_user_id) or "owner"
        
        # Remove from pending
        self.pending_registrations.remove(registration)
        
        # Update user state
        self.set_user_state(registration['user_id'], UserState.IDLE)
        
        logger.info(f"Approved registration for NIK {nik} by {approver_role} {approved_by_user_id}")
        return {
            "success": True, 
            "action": "approved", 
            "user_data": registration, 
            "approver_role": approver_role, 
            "approver_nik": approver_nik,
            "approver_user_id": approved_by_user_id
        }

    def reject_registration(self, nik: str, rejected_by_user_id: int) -> Dict:
        """Reject user registration and return status info"""
        registration = None
        for pending in self.pending_registrations:
            if pending['nik'] == nik:
                registration = pending
                break
        
        if not registration:
            return {"success": False, "reason": "not_found"}
        
        # Get rejector details
        rejector_role = "owner" if self.is_owner(rejected_by_user_id) else "admin"
        rejector_nik = self.get_user_nik(rejected_by_user_id) or "owner"
        
        # Set user state to rejected (allows re-registration)
        self.set_user_state(registration['user_id'], UserState.REJECTED)
        
        # Remove from pending
        self.pending_registrations.remove(registration)
        
        logger.info(f"Rejected registration for NIK {nik} by {rejector_role} {rejected_by_user_id}")
        return {
            "success": True, 
            "action": "rejected", 
            "user_data": registration, 
            "rejector_role": rejector_role, 
            "rejector_nik": rejector_nik,
            "rejector_user_id": rejected_by_user_id
        }

    def get_user_role(self, user_id: int) -> Optional[UserRole]:
        """Get user role"""
        if self.is_owner(user_id):
            return UserRole.OWNER
        
        for nik, user_data in self.registered_users.items():
            if user_data.get('user_id') == user_id:
                if nik in self.admins:
                    return UserRole.ADMIN
                return UserRole.EMPLOYEE
        
        return None

    def get_user_nik(self, user_id: int) -> Optional[str]:
        """Get user NIK by user_id"""
        for nik, user_data in self.registered_users.items():
            if user_data.get('user_id') == user_id:
                return nik
        return None

    def get_user_by_nik(self, nik: str) -> Optional[Dict]:
        """Get user data by NIK"""
        return self.registered_users.get(nik)

    def get_pending_registrations(self) -> List[Dict]:
        """Get all pending registrations"""
        return self.pending_registrations.copy()

    def is_user_registered(self, user_id: int) -> bool:
        """Check if user is registered and approved"""
        for nik, user_data in self.registered_users.items():
            if user_data.get('user_id') == user_id:
                return True
        return False

    def is_user_pending(self, user_id: int) -> bool:
        """Check if user has pending registration"""
        for pending in self.pending_registrations:
            if pending['user_id'] == user_id:
                return True
        return False

    def _ensure_user_data(self, chat_id: int):
        """Ensure user data structure exists"""
        if chat_id not in self.user_states:
            # Determine initial state based on registration status
            if self.is_owner(chat_id):
                initial_state = UserState.IDLE
            elif self.is_user_registered(chat_id):
                initial_state = UserState.IDLE
            elif self.is_user_pending(chat_id):
                initial_state = UserState.PENDING_APPROVAL
            else:
                initial_state = UserState.UNREGISTERED

            self.user_states[chat_id] = {
                'state': initial_state,
                'kendala_type': None,
                'parsed_data': None,
                'last_row': 0,
                'sheet_name': None,
                'media_urls': {},
                'media_step': 0,
                'last_activity': time.time(),
                'nik': self.get_user_nik(chat_id)  # Store user's NIK
            }

    def set_user_state(self, chat_id: int, state: UserState):
        """Set user state"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['state'] = state
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} state set to {state.value}")

    def get_user_state(self, chat_id: int) -> UserState:
        """Get user state"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['state']

    def set_user_kendala_type(self, chat_id: int, kendala_type: KendalaType):
        """Set user kendala type"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['kendala_type'] = kendala_type
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} kendala type set to {kendala_type.value}")

    def get_user_kendala_type(self, chat_id: int) -> Optional[KendalaType]:
        """Get user kendala type"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['kendala_type']

    def set_user_parsed_data(self, chat_id: int, parsed_data: Dict):
        """Set user parsed data"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['parsed_data'] = parsed_data
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} parsed data set")

    def get_user_parsed_data(self, chat_id: int) -> Optional[Dict]:
        """Get user parsed data"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['parsed_data']

    def set_user_last_row(self, chat_id: int, last_row: int):
        """Set user last row number"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['last_row'] = last_row
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} last row set to {last_row}")

    def get_user_last_row(self, chat_id: int) -> int:
        """Get user last row number"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['last_row']

    def set_user_sheet_name(self, chat_id: int, sheet_name: str):
        """Set user sheet name"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['sheet_name'] = sheet_name
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} sheet name set to {sheet_name}")

    def get_user_sheet_name(self, chat_id: int) -> Optional[str]:
        """Get user sheet name"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['sheet_name']

    def add_user_media_url(self, chat_id: int, field_name: str, media_url: str):
        """Add media URL to user data"""
        self._ensure_user_data(chat_id)
        
        if field_name not in self.user_states[chat_id]['media_urls']:
            self.user_states[chat_id]['media_urls'][field_name] = []
        
        self.user_states[chat_id]['media_urls'][field_name].append(media_url)
        self.user_states[chat_id]['last_activity'] = time.time()
        
        logger.info(f"User {chat_id} added media URL for {field_name}: {media_url}")

    def get_user_media_urls(self, chat_id: int) -> Dict[str, List[str]]:
        """Get user media URLs"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['media_urls']

    def get_user_media_count(self, chat_id: int) -> int:
        """Get total count of user media"""
        media_urls = self.get_user_media_urls(chat_id)
        total = sum(len(urls) for urls in media_urls.values())
        return total

    def set_user_media_step(self, chat_id: int, step: int):
        """Set user media step"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['media_step'] = step
        self.user_states[chat_id]['last_activity'] = time.time()
        logger.info(f"User {chat_id} media step set to {step}")

    def get_user_media_step(self, chat_id: int) -> int:
        """Get user media step"""
        self._ensure_user_data(chat_id)
        return self.user_states[chat_id]['media_step']

    def increment_user_media_step(self, chat_id: int):
        """Increment user media step"""
        self._ensure_user_data(chat_id)
        self.user_states[chat_id]['media_step'] += 1
        self.user_states[chat_id]['last_activity'] = time.time()
        new_step = self.user_states[chat_id]['media_step']
        logger.info(f"User {chat_id} media step incremented to {new_step}")

    def clear_user_data(self, chat_id: int):
        """Clear all user data except registration info"""
        if chat_id in self.user_states:
            # Keep registration status but clear work data
            current_state = self.get_user_state(chat_id)
            if current_state in [UserState.UNREGISTERED, UserState.PENDING_APPROVAL, UserState.REJECTED]:
                # Don't change registration states
                pass
            else:
                # Reset to IDLE for registered users
                current_state = UserState.IDLE
            
            self.user_states[chat_id] = {
                'state': current_state,
                'kendala_type': None,
                'parsed_data': None,
                'last_row': 0,
                'sheet_name': None,
                'media_urls': {},
                'media_step': 0,
                'last_activity': time.time(),
                'nik': self.get_user_nik(chat_id)
            }
            logger.info(f"User {chat_id} data cleared")

    def check_rate_limit(self, chat_id: int, rate_limit_seconds: int) -> bool:
        """Check if user is rate limited"""
        self._ensure_user_data(chat_id)
        
        current_time = time.time()
        last_activity = self.user_states[chat_id]['last_activity']
        
        if current_time - last_activity < rate_limit_seconds:
            logger.warning(f"User {chat_id} rate limited")
            return False
        
        self.user_states[chat_id]['last_activity'] = current_time
        return True

    def debug_user_state(self, chat_id: int):
        """Debug user state information"""
        if chat_id in self.user_states:
            user_data = self.user_states[chat_id]
            logger.debug(
                f"User {chat_id} debug - State: {user_data['state'].value}, "
                f"Kendala: {user_data['kendala_type'].value if user_data['kendala_type'] else None}, "
                f"Media step: {user_data['media_step']}, "
                f"Sheet: {user_data['sheet_name']}, "
                f"NIK: {user_data.get('nik', 'None')}, "
                f"Media count: {sum(len(urls) for urls in user_data['media_urls'].values())}"
            )
        else:
            logger.debug(f"User {chat_id} has no state data")

    def cleanup_old_sessions(self, max_age_hours: int = 24):
        """Clean up old user sessions"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        expired_users = []
        for chat_id, user_data in self.user_states.items():
            if current_time - user_data['last_activity'] > max_age_seconds:
                expired_users.append(chat_id)
        
        for chat_id in expired_users:
            del self.user_states[chat_id]
            logger.info(f"Cleaned up expired session for user {chat_id}")
        
        if expired_users:
            logger.info(f"Cleaned up {len(expired_users)} expired sessions")

    def get_active_users_count(self) -> int:
        """Get count of active users"""
        return len(self.user_states)

    def get_user_stats(self) -> Dict:
        """Get user statistics"""
        stats = {
            'total_active': len(self.user_states),
            'total_registered': len(self.registered_users),
            'pending_registrations': len(self.pending_registrations),
            'admins': len(self.admins),
            'states': {},
            'kendala_types': {}
        }
        
        for user_data in self.user_states.values():
            # Count states
            state = user_data['state'].value
            stats['states'][state] = stats['states'].get(state, 0) + 1
            
            # Count kendala types
            if user_data['kendala_type']:
                kendala = user_data['kendala_type'].value
                stats['kendala_types'][kendala] = stats['kendala_types'].get(kendala, 0) + 1
        
        return stats

    def get_admin_list(self) -> List[Dict]:
        """Get list of admins with details"""
        admin_list = []
        for nik in self.admins:
            if nik in self.registered_users:
                user_data = self.registered_users[nik]
                admin_list.append({
                    'nik': nik,
                    'user_id': user_data.get('user_id'),
                    'username': user_data.get('username'),
                    'role': 'admin'
                })
        return admin_list

    def get_all_users_list(self) -> List[Dict]:
        """Get list of all registered users with details"""
        user_list = []
        for nik, user_data in self.registered_users.items():
            role = "admin" if nik in self.admins else "employee"
            user_list.append({
                'nik': nik,
                'user_id': user_data.get('user_id'),
                'username': user_data.get('username'),
                'role': role,
                'status': user_data.get('status', 'approved'),
                'created_at': user_data.get('created_at')
            })
        return user_list


# Global instance
user_manager = UserStateManager()