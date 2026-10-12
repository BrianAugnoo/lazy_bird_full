import lazy_bird.crud.conversation as conversation_crud
import lazy_bird.crud.message as message_crud
from lazy_bird.schemas.message import MessageIn
from lazy_bird.crud.profile import get as get_profile

class System:
    def __init__(self, session, conversation_id: int):
        self.session = session
        self.last_message = self._get_last_message(conversation_id)
        self.instructions = conversation_crud.get_instructions(conversation_id)
        self.editable_roles = self.last_message.role == "user"
        sys_hooks = lambda: self.last_message.hooks.get("system")
        if not sys_hooks() and self.editable_roles:
            self.last_message.hooks["system"] = {}
            message_crud.edit_hooks(self.last_message.hooks, self.last_message.id)
        self.sys_hooks = sys_hooks()
        
    def date(self):
        """Add Date: to the user prompt"""
        if self.editable_roles:
            from datetime import datetime
            now = datetime.now()
            date_str = now.strftime("%Y-%m-%d %H:%M:%S")
            self.sys_hooks["date"] = f"Date: {date_str}"
            message_crud.edit_hooks(self.last_message.hooks, self.last_message.id)
            
    def environment_information(self):
        """Add environment information to the system prompt"""
        if self.instructions:
            sys_hooks = lambda: self.instructions.hooks.get("system")
            if not sys_hooks():
                self.instructions.hooks["system"] = {}
            sys_hooks()["Environment Information"] = {
                "os_info": self._get_os_info(),
                "harness": "Lazy Bird (development stage)",
                "wokspace": self.session.meta.get("workspace"),
            }
            message_crud.edit_hooks(self.instructions.hooks, self.instructions.id)
            
    def user_information(self):
        """Add user information to the system prompt"""
        if self.instructions:
            sys_hooks = lambda: self.instructions.hooks.get("system")
            if not sys_hooks():
                self.instructions.hooks["system"] = {}
                user = get_profile().user
            sys_hooks()["User Information"] = {
                "Name": user.name,
                "Email": user.email,
                "Age": user.age,
                "languages": " ,".join(user.languages) if user.languages else None,
                "Description": user.description,
            }
            message_crud.edit_hooks(self.instructions.hooks, self.instructions.id)
            
    def _get_last_message(self, conversation_id: int):
        """Get the last message in the conversation."""
        messages = message_crud.for_conversation(conversation_id)
        return messages[-1] if messages else None
    
    @staticmethod
    def _get_os_info():
        import platform
        system = platform.system()

        info = {
            "system": system,                 
            "version": platform.version(),
        }

        if system == "Darwin":
            info["os_version"] = platform.mac_ver()[0]

        elif system == "Windows":
            release, version, service_pack, _ = platform.win32_ver()
            info["os_version"] = version
            info["windows_release"] = release
            info["service_pack"] = service_pack

        elif system == "Linux":
            get_distro = getattr(platform, "freedesktop_os_release", None)

            if get_distro is not None:
                try:
                    distro = get_distro()
                    info["distribution"] = distro.get("PRETTY_NAME", "")
                    info["distribution_id"] = distro.get("ID", "")
                    info["os_version"] = distro.get("VERSION_ID", "")
                except OSError:
                    pass 

        return info
    
hooks = [System]