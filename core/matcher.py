import yaml
import os
import re

class Matcher:
    def __init__(self, config_path: str = None):
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), '..', 'config', 'alertas.yaml')
            
        with open(config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f)
            
        self.perfiles = self.config.get('perfiles', [])
        
    def match(self, texto: str) -> list[str]:
        """
        Retorna una lista con los nombres de los perfiles que hacen match con el texto dado.
        """
        if not texto:
            return []
            
        texto = texto.lower()
        perfiles_matched = []
        
        for perfil in self.perfiles:
            nombre = perfil.get('nombre', 'Desconocido')
            keywords = [k.lower() for k in perfil.get('keywords', [])]
            exclusiones = [e.lower() for e in perfil.get('exclusiones', [])]
            
            # Check exclusions first
            excluded = any(re.search(r'\b' + re.escape(exc) + r'\b', texto) for exc in exclusiones if exc)
            if excluded:
                continue
                
            # If no keywords, it matches everything (unless excluded)
            if not keywords:
                perfiles_matched.append(nombre)
                continue
                
            # Check if any keyword is present
            matched = any(re.search(r'\b' + re.escape(kw) + r'\b', texto) for kw in keywords if kw)
            if matched:
                perfiles_matched.append(nombre)
                
        return perfiles_matched
