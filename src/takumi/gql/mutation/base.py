import graphene


class Mutation(graphene.Mutation):
    ok = graphene.Boolean(required=True)

    def mutate(root, info, *args, **kwargs):
        raise NotImplementedError
