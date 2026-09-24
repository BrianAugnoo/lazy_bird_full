## Bugs / incoherence:

1. pas besoin de le corriger car il ne s'agit que d'une fonction test dans tout les cas il va etre retirer
2. effectivement on ne peut pas envoyer directement callable, il faut que l'engine les retire avant l'envoie et ne l'utilise qu'en local
3. effectivement il faut ajouter 2 nouveau role "tool-calling" et "tool-response" pour une identification plus facile, et c'est le role des chat() des engines d'utiliser les termes exacte car il y en aurait plusieur

## Point bloquant

- A. oui la structure que tu a suggerer est parfaite
- B. oui chat doit retourner toutes les informations, mais single_turn va etre retirer donc pas besoin de le modifier
- C. exactement ton hypothese est correct
- D. l'execution de tools se font touts de maniere synchrone
- E. ajoute un params "max_iter" a agentic_loop avec un valeur par defaut fixer a 20
- F. oui on injecte un message d'erreur pour laisser le model se corriger
- G. je n'ais pas tres bien compris la question mais ConversationCRUD.messages() return  la liste des MessageOut  apartenant a conversation dans son integralites du plus ancien a plus, si il y a un prompt systeme c'est toujours le plus ancien (le premier) avec role: "system" et le content se trouve dans meta et c'est l'unique, d'autres ficher de plus haut niveau gere ca.

## suggestion de design
- 1. oui c'est ce qu'il faut faire
- 2. oui chaque chaque engine doivent convertir les messages dans le format le plus optimal
- 3. exact
- 4. exact
