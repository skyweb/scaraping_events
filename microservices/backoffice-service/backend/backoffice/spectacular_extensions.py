from drf_spectacular.extensions import OpenApiAuthenticationExtension


class ApisixConsumerAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "backoffice.authentication.ApisixConsumerAuthentication"
    name = ["ApisixConsumerPlan", "ApisixConsumerUsername"]

    def get_security_definition(self, auto_schema):
        return [
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Consumer-Plan",
                "description": "Piano del consumer API iniettato da APISIX.",
            },
            {
                "type": "apiKey",
                "in": "header",
                "name": "X-Consumer-Username",
                "description": "Username del consumer API iniettato da APISIX.",
            },
        ]


class KeycloakJWTAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "backoffice.authentication.KeycloakJWTAuthentication"
    name = "KeycloakBearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "JWT Bearer emesso da Keycloak.",
        }
